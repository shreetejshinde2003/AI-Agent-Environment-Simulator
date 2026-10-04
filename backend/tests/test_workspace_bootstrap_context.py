"""User-bound bootstrap control flow and policy predicates, without a PG server.

Predicate evaluation on SQLite is NOT PostgreSQL RLS enforcement verification.
The separate opt-in suite exercises FORCE RLS and real pooled connections.
"""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import text, update

from app.security.postgres_rls import POSTGRES_RLS_POLICIES
from app.security.tenant_db_context import (
    BootstrapSessionContext, TenantContextError, apply_bootstrap_session_context,
    apply_tenant_session_context, bootstrap_transaction, invitation_transaction,
    apply_invitation_membership_context, recovery_catalog_transaction,
    STARTUP_RECOVERY_PRINCIPAL,
)
from app.storage import database, models as dbm
from app.storage.database import Repository
from app.security.rbac import resolve_workspace_authorization, WorkspaceRole
from test_tenant_db_context import RecordingEngine, RecordingPostgresConnection
from test_tenant_repository_primitives import make_user


def test_bootstrap_sets_only_identity_and_clears_workspace_and_operation_capabilities():
    connection = RecordingPostgresConnection()
    context = apply_bootstrap_session_context(connection, user_id="USR-a")
    assert context == BootstrapSessionContext("USR-a")
    sql, parameters = connection.calls[-1]
    assert sql.count("true") == 5
    assert parameters["user_id"] == "USR-a"
    for key in ("workspace_id", "invitation_digest", "invitation_workspace_id", "recovery_owner_user_id"):
        assert parameters[key] == ""
    assert "USR-a" not in sql
    apply_tenant_session_context(connection, workspace_id="WS-a", user_id="USR-a")
    assert connection.calls[-1][1]["workspace_id"] == "WS-a"
    assert connection.calls[-1][1]["invitation_digest"] == ""


@pytest.mark.parametrize("user_id", [None, "", " ", " USR-a", "USR-a\x00", "x" * 256])
def test_invalid_bootstrap_identity_is_rejected_before_checkout(user_id):
    engine = RecordingEngine(RecordingPostgresConnection())
    with pytest.raises(TenantContextError):
        with bootstrap_transaction(engine, user_id=user_id):
            pytest.fail("invalid bootstrap yielded")
    assert not engine.entered


def test_bootstrap_transaction_propagates_errors_and_exits():
    engine = RecordingEngine(RecordingPostgresConnection())
    with pytest.raises(RuntimeError, match="rollback"):
        with bootstrap_transaction(engine, user_id="USR-a"):
            raise RuntimeError("rollback")
    assert engine.entered and engine.exited


def test_invitation_and_recovery_contexts_are_distinct_and_bounded():
    connection = RecordingPostgresConnection()
    engine = RecordingEngine(connection)
    with invitation_transaction(engine, user_id="USR-a", digest="a" * 64):
        assert connection.calls[-1][1]["workspace_id"] == ""
        assert connection.calls[-1][1]["invitation_workspace_id"] == ""
        apply_invitation_membership_context(connection, user_id="USR-a", workspace_id="WS-code", digest="a" * 64)
        assert connection.calls[-1][1]["invitation_workspace_id"] == "WS-code"
        assert connection.calls[-1][1]["workspace_id"] == ""
    with recovery_catalog_transaction(engine, owner_user_id="USR-b"):
        params = connection.calls[-1][1]
        assert params["user_id"] == STARTUP_RECOVERY_PRINCIPAL
        assert params["recovery_owner_user_id"] == "USR-b"
        assert params["workspace_id"] == params["invitation_digest"] == ""
    engine.entered = False
    with pytest.raises(TenantContextError):
        with invitation_transaction(engine, user_id="USR-a", digest="bad"):
            pass
    assert not engine.entered


@pytest.fixture
def repo(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'bootstrap.db'}")
    repo.initialize()
    for uid in ("USR-a", "USR-b", "USR-c"):
        repo.save_user(make_user(uid))
        repo.ensure_personal_workspace(uid)
    yield repo
    repo.engine.dispose()


def policy_rows(repo, table, settings):
    """Evaluate the actual SQL predicate with SQLite's current_setting shim."""
    policy = next(p for p in POSTGRES_RLS_POLICIES if p.table == table)
    with repo.engine.connect() as connection:
        connection.connection.driver_connection.create_function(
            "current_setting", 2, lambda name, missing_ok: settings.get(name)
        )
        return connection.execute(text(f'SELECT * FROM "{table}" WHERE {policy.using_sql}')).mappings().all()


def test_actual_bootstrap_predicates_hide_other_personal_unrelated_and_inactive_orgs(repo):
    org, code = repo.create_organization(creator_user_id="USR-b", name="Private Org")
    own = repo.get_personal_workspace("USR-a")["id"]
    settings = {"app.current_user_id": "USR-a"}
    assert [r["id"] for r in policy_rows(repo, "workspaces", settings)] == [own]
    assert policy_rows(repo, "organization_memberships", settings) == []
    assert policy_rows(repo, "workspaces", {}) == []
    assert policy_rows(repo, "organization_memberships", {}) == []
    repo.join_organization(user_id="USR-a", join_code=code)
    assert {r["id"] for r in policy_rows(repo, "workspaces", settings)} == {own, org["id"]}
    with repo.engine.begin() as connection:
        connection.execute(update(dbm.organization_memberships).where(
            dbm.organization_memberships.c.user_id == "USR-a").values(active=False))
    assert [r["id"] for r in policy_rows(repo, "workspaces", settings)] == [own]
    assert policy_rows(repo, "organization_memberships", settings) == []
    assert repo.get_workspace(org["id"], user_id="USR-a") is None


def test_selected_workspace_without_user_fails_closed_and_with_user_is_narrow(repo):
    org, _ = repo.create_organization(creator_user_id="USR-a", name="Team")
    settings = {"app.current_workspace_id": org["id"]}
    assert policy_rows(repo, "workspaces", settings) == []
    assert policy_rows(repo, "organization_memberships", settings) == []
    settings["app.current_user_id"] = "USR-a"
    assert [row["id"] for row in policy_rows(repo, "workspaces", settings)] == [org["id"]]
    assert {row["workspace_id"] for row in policy_rows(repo, "organization_memberships", settings)} == {org["id"]}


def test_bootstrap_membership_write_predicate_has_no_implicit_role_grant(repo):
    org, _ = repo.create_organization(creator_user_id="USR-a", name="Team")
    policy = next(p for p in POSTGRES_RLS_POLICIES if p.table == "organization_memberships")
    settings = {"app.current_user_id": "USR-a"}
    with repo.engine.connect() as connection:
        connection.connection.driver_connection.create_function("current_setting", 2, lambda name, ok: settings.get(name))
        assert connection.execute(text(f"SELECT * FROM organization_memberships WHERE {policy.check_sql}")).all() == []
        settings["app.current_workspace_id"] = org["id"]
        assert len(connection.execute(text(f"SELECT * FROM organization_memberships WHERE {policy.check_sql}")).all()) == 1


def test_tenant_to_bootstrap_transition_clears_selected_workspace():
    connection = RecordingPostgresConnection()
    apply_tenant_session_context(connection, workspace_id="WS-a", user_id="USR-a")
    apply_bootstrap_session_context(connection, user_id="USR-b")
    assert connection.calls[-1][1]["user_id"] == "USR-b"
    assert connection.calls[-1][1]["workspace_id"] == ""


def test_maintenance_catalog_predicate_is_owner_bounded_and_not_normal_discovery(repo):
    org, _ = repo.create_organization(creator_user_id="USR-b", name="Orphan Org")
    with repo.engine.begin() as connection:
        connection.execute(update(dbm.workspaces).where(dbm.workspaces.c.id == org["id"]).values(active=False))
        connection.execute(update(dbm.organization_memberships).where(
            dbm.organization_memberships.c.workspace_id == org["id"]).values(active=False))
    settings = {"app.current_user_id": STARTUP_RECOVERY_PRINCIPAL, "app.recovery_owner_user_id": "USR-b"}
    rows = policy_rows(repo, "workspaces", settings)
    assert {r["id"] for r in rows} == {org["id"], repo.get_personal_workspace("USR-b")["id"]}
    assert policy_rows(repo, "workspaces", {"app.current_user_id": STARTUP_RECOVERY_PRINCIPAL}) == []
    # A human identity does not acquire maintenance visibility from this setting.
    settings["app.current_user_id"] = "USR-a"
    assert [r["id"] for r in policy_rows(repo, "workspaces", settings)] == [repo.get_personal_workspace("USR-a")["id"]]


def test_sqlite_authorization_and_personal_provisioning_remain_compatible(repo):
    a = repo.ensure_personal_workspace("USR-a")
    assert repo.ensure_personal_workspace("USR-a") == a
    b = repo.get_personal_workspace("USR-b")
    assert repo.get_workspace(b["id"], user_id="USR-a") is None
    assert repo.get_workspace(b["id"]) == b  # Explicit local fixture compatibility.
    org, code = repo.create_organization(creator_user_id="USR-b", name="Team")
    repo.join_organization(user_id="USR-a", join_code=code)
    assert resolve_workspace_authorization(repo, user_id="USR-a", workspace_id=org["id"]).role == WorkspaceRole.MEMBER
    assert resolve_workspace_authorization(repo, user_id="USR-b", workspace_id=org["id"]).role == WorkspaceRole.OWNER
    assert len(repo.list_organization_memberships(org["id"], actor_user_id="USR-b")) == 2
    with pytest.raises(PermissionError):
        repo.list_organization_memberships(org["id"], actor_user_id="USR-c")
    repo.change_organization_membership_role(workspace_id=org["id"], actor_user_id="USR-b", target_user_id="USR-a", new_role="admin")
    assert resolve_workspace_authorization(repo, user_id="USR-a", workspace_id=org["id"]).role == WorkspaceRole.ADMIN


def test_repository_carries_actor_not_target_identity_for_member_inspection(repo, monkeypatch):
    org, code = repo.create_organization(creator_user_id="USR-b", name="Team")
    repo.join_organization(user_id="USR-a", join_code=code)
    contexts = []
    original = database.tenant_transaction
    @contextmanager
    def record(engine, *, workspace_id, user_id):
        contexts.append((workspace_id, user_id))
        with original(engine, workspace_id=workspace_id, user_id=user_id) as connection:
            yield connection
    monkeypatch.setattr(database, "tenant_transaction", record)
    assert repo.get_organization_membership(org["id"], "USR-a", actor_user_id="USR-b")["user_id"] == "USR-a"
    assert contexts == [(org["id"], "USR-b")]


@pytest.mark.parametrize("method,args", [
    ("get_workspace", ("WS-a",)), ("save_workspace", ({},)),
    ("save_organization_membership", ({},)), ("list_organization_memberships", ("WS-a",)),
])
def test_unscoped_pg_workspace_compatibility_methods_fail_before_connection(method, args):
    repo = Repository("postgresql://unused@localhost/unused")
    repo._engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    repo._engine_url = repo.url
    with pytest.raises(TenantContextError):
        getattr(repo, method)(*args)
