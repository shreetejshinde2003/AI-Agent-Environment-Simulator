"""HR-role tenant transaction wiring and adversarial SQLite/predicate tests.

SQL predicate checks here are not real PostgreSQL FORCE RLS verification.
No HTTP provider, Google or model calls are needed.
"""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import event, insert, text, update
from fastapi.testclient import TestClient

from app.security.hr_roles import HRHumanPermission, resolve_hr_human_authorization
from app.security.postgres_rls import POSTGRES_RLS_POLICIES, POLICY_NAME, WRITE_POLICY_NAME
from app.security.rbac import AuthorizationError, Permission, resolve_workspace_authorization
from app.security.tenant_db_context import TenantContextError
from app.storage import database, models as dbm
from app.storage.database import Repository
from test_tenant_repository_primitives import make_user


@pytest.fixture
def orgs(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'hr-tenancy.db'}")
    repo.initialize()
    for uid in ("owner", "admin", "member", "outsider"):
        repo.save_user(make_user(uid))
        repo.ensure_personal_workspace(uid)
    a, code_a = repo.create_organization(creator_user_id="owner", name="Organization A")
    b, code_b = repo.create_organization(creator_user_id="outsider", name="Organization B")
    for uid in ("admin", "member"):
        repo.join_organization(user_id=uid, join_code=code_a)
    repo.join_organization(user_id="member", join_code=code_b)
    repo.change_organization_membership_role(workspace_id=a["id"], actor_user_id="owner", target_user_id="admin", new_role="admin")
    yield repo, a["id"], b["id"]
    repo.engine.dispose()


def assign(repo, ws, *, actor="owner", target="member", role="hr_approver"):
    return repo.assign_organization_human_role(workspace_id=ws, actor_user_id=actor, target_user_id=target, human_role=role)


def policy_rows(repo, settings, *, expression="using_sql"):
    policy = next(p for p in POSTGRES_RLS_POLICIES if p.table == "organization_human_role_assignments")
    with repo.engine.connect() as connection:
        connection.connection.driver_connection.create_function("current_setting", 2, lambda name, ok: settings.get(name))
        return connection.execute(text(
            f"SELECT * FROM organization_human_role_assignments WHERE {getattr(policy, expression)}"
        )).mappings().all()


def test_hr_reads_and_writes_carry_actor_identity_and_explicit_workspace(orgs, monkeypatch):
    repo, a, _ = orgs
    contexts = []
    active = []
    original = database.tenant_transaction
    @contextmanager
    def record(engine, *, workspace_id, user_id):
        contexts.append((workspace_id, user_id))
        with original(engine, workspace_id=workspace_id, user_id=user_id) as connection:
            active.append((workspace_id, user_id))
            try:
                yield connection
            finally:
                active.clear()
    def observe(connection, statement, *args):
        if "organization_human_role_assignments" in str(statement):
            assert active == [(a, "admin")]
            if getattr(statement, "is_select", False) or getattr(statement, "is_update", False):
                assert "organization_human_role_assignments.workspace_id =" in str(statement)
    monkeypatch.setattr(database, "tenant_transaction", record)
    event.listen(repo.engine, "before_execute", observe)
    try:
        assignment = assign(repo, a, actor="admin")
        assert assignment["assigned_by_user_id"] == "admin" and assignment["user_id"] == "member"
        rows = repo.list_organization_human_roles(a, actor_user_id="admin", user_id="member")
        assert rows == [assignment]
        repo.deactivate_organization_human_role(workspace_id=a, actor_user_id="admin", target_user_id="member", human_role="hr_approver")
        assert contexts == [(a, "admin")] * 3
    finally:
        event.remove(repo.engine, "before_execute", observe)


def test_cross_org_domain_roles_do_not_expand_iam_or_other_domain_permissions(orgs):
    repo, a, b = orgs
    assign(repo, a)
    assert resolve_hr_human_authorization(repo, user_id="member", workspace_id=a).allows(HRHumanPermission.JD_APPROVE)
    assert resolve_hr_human_authorization(repo, user_id="member", workspace_id=b).roles == frozenset()
    assert not resolve_workspace_authorization(repo, user_id="member", workspace_id=a).allows(Permission.ORGANIZATION_HUMAN_ROLES_MANAGE)
    with pytest.raises(AuthorizationError):
        assign(repo, a, actor="member", target="member", role="hr_recruiter")
    with pytest.raises(AuthorizationError):
        assign(repo, b, actor="owner")
    with pytest.raises(AuthorizationError):
        repo.list_organization_human_roles(b, actor_user_id="owner")


def test_admin_can_manage_hr_roles_but_cannot_promote_iam_ownership(orgs):
    repo, a, b = orgs
    assign(repo, a, actor="admin", target="owner", role="hr_recruiter")
    assert resolve_hr_human_authorization(repo, user_id="owner", workspace_id=a).allows(HRHumanPermission.JD_DRAFT_EDIT)
    with pytest.raises(AuthorizationError):
        repo.change_organization_membership_role(workspace_id=a, actor_user_id="admin", target_user_id="member", new_role="owner")
    with pytest.raises(AuthorizationError):
        assign(repo, b, actor="admin")
    assert repo.get_organization_membership(a, "admin")["membership_role"] == "admin"


def test_member_reads_only_own_active_roles_not_management_listing_or_history(orgs):
    repo, a, _ = orgs
    assign(repo, a)
    assert len(repo.list_organization_human_roles(a, actor_user_id="member", user_id="member")) == 1
    for filters in ({}, {"user_id": "owner"}, {"user_id": "member", "active_only": False}):
        with pytest.raises(AuthorizationError):
            repo.list_organization_human_roles(a, actor_user_id="member", **filters)


def test_membership_and_assignment_deactivation_remove_permissions_without_cache(orgs):
    repo, a, _ = orgs
    assign(repo, a)
    assert resolve_hr_human_authorization(repo, user_id="member", workspace_id=a).roles
    repo.deactivate_organization_human_role(workspace_id=a, actor_user_id="admin", target_user_id="member", human_role="hr_approver")
    assert not resolve_hr_human_authorization(repo, user_id="member", workspace_id=a).roles
    assert repo.list_organization_human_roles(a, actor_user_id="admin", active_only=False)[0]["active"] is False
    assign(repo, a, actor="admin")
    with repo.engine.begin() as connection:
        connection.execute(update(dbm.organization_memberships).where(
            dbm.organization_memberships.c.workspace_id == a, dbm.organization_memberships.c.user_id == "member",
        ).values(active=False))
    assert not resolve_hr_human_authorization(repo, user_id="member", workspace_id=a).roles
    assert policy_rows(repo, {"app.current_workspace_id": a, "app.current_user_id": "member"}) == []
    with pytest.raises(AuthorizationError):
        assign(repo, a, actor="admin")
    # Managers can still clean up saved history after target membership loss.
    assert repo.deactivate_organization_human_role(workspace_id=a, actor_user_id="admin", target_user_id="member", human_role="hr_approver")["active"] is False


def test_personal_workspace_never_has_hr_domain_semantics_even_with_legacy_bad_row(orgs):
    repo, a, _ = orgs
    assignment = assign(repo, a)
    personal = repo.get_personal_workspace("member")["id"]
    with repo.engine.begin() as connection:
        connection.execute(insert(dbm.organization_human_role_assignments).values(**{**assignment, "workspace_id": personal}))
    assert not resolve_hr_human_authorization(repo, user_id="member", workspace_id=personal).roles
    assert policy_rows(repo, {"app.current_workspace_id": personal, "app.current_user_id": "member"}) == []
    with pytest.raises(AuthorizationError):
        assign(repo, personal, actor="member", target="member")


def test_actual_policy_predicates_are_user_and_org_scoped_and_reads_are_not_writes(orgs):
    repo, a, b = orgs
    assign(repo, a)
    assign(repo, a, target="admin", role="hr_reviewer")
    assign(repo, b, actor="outsider", role="hr_recruiter")
    for settings in ({}, {"app.current_user_id": "owner"}, {"app.current_workspace_id": a}):
        assert policy_rows(repo, settings) == []
        assert policy_rows(repo, settings, expression="write_using_sql") == []
    assert {row["workspace_id"] for row in policy_rows(repo, {"app.current_workspace_id": a, "app.current_user_id": "owner"})} == {a}
    assert policy_rows(repo, {"app.current_workspace_id": b, "app.current_user_id": "owner"}) == []
    member = {"app.current_workspace_id": a, "app.current_user_id": "member"}
    assert [r["user_id"] for r in policy_rows(repo, member)] == ["member"]
    assert policy_rows(repo, member, expression="write_using_sql") == []
    assert policy_rows(repo, member, expression="write_check_sql") == []
    policy = next(p for p in POSTGRES_RLS_POLICIES if p.table == "organization_human_role_assignments")
    assert policy.policy_names == {POLICY_NAME, WRITE_POLICY_NAME}
    assert "FOR SELECT" in policy.ddl()[-2]
    assert "FOR ALL" in policy.ddl()[-1] and "hr_actor.membership_role IN ('owner', 'admin')" in policy.ddl()[-1]


def test_write_check_requires_real_actor_and_active_target_except_cleanup(orgs):
    repo, a, _ = orgs
    assign(repo, a)
    owner = {"app.current_workspace_id": a, "app.current_user_id": "owner"}
    admin = {"app.current_workspace_id": a, "app.current_user_id": "admin"}
    assert len(policy_rows(repo, owner, expression="write_check_sql")) == 1
    # A manager still cannot write a row attributed to a different actor.
    assert policy_rows(repo, admin, expression="write_check_sql") == []
    assign(repo, a, actor="admin")
    assert len(policy_rows(repo, admin, expression="write_check_sql")) == 1
    with repo.engine.begin() as connection:
        connection.execute(update(dbm.organization_memberships).where(
            dbm.organization_memberships.c.workspace_id == a,
            dbm.organization_memberships.c.user_id == "member",
        ).values(active=False))
    assert policy_rows(repo, admin, expression="write_check_sql") == []
    repo.deactivate_organization_human_role(
        workspace_id=a, actor_user_id="admin", target_user_id="member", human_role="hr_approver",
    )
    assert len(policy_rows(repo, admin, expression="write_check_sql")) == 1
    with repo.engine.begin() as connection:
        connection.execute(update(dbm.workspaces).where(dbm.workspaces.c.id == a).values(active=False))
    assert policy_rows(repo, admin) == []
    assert policy_rows(repo, admin, expression="write_check_sql") == []


@pytest.mark.parametrize("operation", ["assign", "deactivate", "list"])
def test_stale_preflight_admin_role_is_rechecked_inside_transaction(orgs, monkeypatch, operation):
    repo, a, _ = orgs
    assign(repo, a)
    original = database.tenant_transaction
    @contextmanager
    def demote_before_begin(engine, *, workspace_id, user_id):
        with engine.begin() as connection:
            connection.execute(update(dbm.organization_memberships).where(
                dbm.organization_memberships.c.workspace_id == a, dbm.organization_memberships.c.user_id == "admin",
            ).values(membership_role="member"))
        with original(engine, workspace_id=workspace_id, user_id=user_id) as connection:
            yield connection
    monkeypatch.setattr(database, "tenant_transaction", demote_before_begin)
    with pytest.raises(AuthorizationError):
        if operation == "assign":
            assign(repo, a, actor="admin", role="hr_reviewer")
        elif operation == "deactivate":
            repo.deactivate_organization_human_role(workspace_id=a, actor_user_id="admin", target_user_id="member", human_role="hr_approver")
        else:
            repo.list_organization_human_roles(a, actor_user_id="admin")
    assert [r["human_role"] for r in repo.list_organization_human_roles(a)] == ["hr_approver"]
    assert repo.list_organization_human_roles(a)[0]["active"]


def test_revocation_between_bootstrap_and_role_read_returns_empty_authorization(orgs, monkeypatch):
    repo, a, _ = orgs
    assign(repo, a)
    original = repo.list_organization_human_roles
    def revoke_and_read(*args, **kwargs):
        with repo.engine.begin() as connection:
            connection.execute(update(dbm.organization_memberships).where(
                dbm.organization_memberships.c.workspace_id == a, dbm.organization_memberships.c.user_id == "member",
            ).values(active=False))
        return original(*args, **kwargs)
    monkeypatch.setattr(repo, "list_organization_human_roles", revoke_and_read)
    assert not resolve_hr_human_authorization(repo, user_id="member", workspace_id=a).roles


def test_storage_failure_is_not_hidden_as_missing_roles_and_writes_roll_back(orgs, monkeypatch):
    repo, a, _ = orgs
    def fail_after_insert(connection, cursor, statement, *args):
        if statement.startswith("INSERT INTO organization_human_role_assignments"):
            raise RuntimeError("controlled persistence failure")
    event.listen(repo.engine, "after_cursor_execute", fail_after_insert)
    try:
        with pytest.raises(RuntimeError, match="persistence failure"):
            assign(repo, a)
    finally:
        event.remove(repo.engine, "after_cursor_execute", fail_after_insert)
    assert repo.list_organization_human_roles(a) == []
    def broken_read(*args, **kwargs):
        raise RuntimeError("controlled read failure")
    monkeypatch.setattr(repo, "list_organization_human_roles", broken_read)
    with pytest.raises(RuntimeError, match="read failure"):
        resolve_hr_human_authorization(repo, user_id="member", workspace_id=a)


@pytest.mark.parametrize("target", [None, "member"])
def test_pg_legacy_listing_never_infers_principal_from_target_or_connects(target):
    repo = Repository("postgresql://unused@localhost/unused")
    repo._engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    repo._engine_url = repo.url
    with pytest.raises(TenantContextError):
        repo.list_organization_human_roles("WS-a", user_id=target)


@pytest.mark.parametrize("inactive,expected_status", [(True, 404), (False, 403)])
def test_api_listing_rechecks_404_vs_403_after_preflight_revocation(orgs, monkeypatch, inactive, expected_status):
    from app.api.routes import workspaces
    from app.main import app

    repo, a, _ = orgs
    assign(repo, a)
    original = repo.list_organization_human_roles
    def revoke_then_read(*args, **kwargs):
        with repo.engine.begin() as connection:
            connection.execute(update(dbm.organization_memberships).where(
                dbm.organization_memberships.c.workspace_id == a,
                dbm.organization_memberships.c.user_id == "admin",
            ).values(**({"active": False} if inactive else {"membership_role": "member"})))
        return original(*args, **kwargs)
    monkeypatch.setattr(workspaces, "repository", repo)
    monkeypatch.setattr(workspaces.auth, "_authenticated_record", lambda request: (repo.get_user("admin"), {}))
    monkeypatch.setattr(repo, "list_organization_human_roles", revoke_then_read)
    # Do not enter the lifespan: it uses the global simulation repository, not
    # this isolated route fixture. The request never creates/executes a run.
    client = TestClient(app)
    try:
        response = client.get(f"/api/v1/workspaces/organizations/{a}/human-roles")
    finally:
        client.close()
    assert response.status_code == expected_status
    expected_code = "workspace_unavailable" if inactive else "permission_denied"
    assert response.json()["detail"]["code"] == expected_code
