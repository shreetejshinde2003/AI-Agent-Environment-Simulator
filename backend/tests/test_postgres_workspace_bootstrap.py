"""Opt-in real PostgreSQL bootstrap RLS adversarial tests. No provider calls.

Uses the isolated local schema/non-bypass fixture; missing test URL means SKIPPED,
not successful enforcement verification. No production DATABASE_URL is used.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import DBAPIError

from app.security.tenant_db_context import (
    bootstrap_transaction, tenant_transaction, apply_tenant_session_context,
    invitation_transaction, recovery_catalog_transaction,
    CURRENT_USER_SQL, CURRENT_WORKSPACE_SQL, INVITATION_DIGEST_SQL,
    INVITATION_WORKSPACE_SQL, RECOVERY_OWNER_SQL,
)
from app.security.rbac import resolve_workspace_authorization, WorkspaceRole, AuthorizationError
from app.security.workspaces import join_code_digest
from app.storage import models as dbm
from test_postgres_data_plane_integration import pg_repo, seed
from test_phase2_storage import example_task
from test_tenant_repository_primitives import make_user
from app.api.routes.tasks import _mark_interrupted_failed
from app.models.schemas import TaskStatus


def test_live_user_bound_discovery_without_application_filters(pg_repo):
    a = pg_repo.get_personal_workspace("USR-a")
    b = pg_repo.get_personal_workspace("USR-b")
    org, code = pg_repo.create_organization(creator_user_id="USR-b", name="Hidden Organization")
    with bootstrap_transaction(pg_repo.engine, user_id="USR-a") as connection:
        assert connection.execute(select(dbm.workspaces.c.id)).scalars().all() == [a["id"]]
        assert connection.execute(select(dbm.organization_memberships)).all() == []
        assert connection.execute(select(dbm.workspaces).where(dbm.workspaces.c.id == b["id"])).all() == []
    assert pg_repo.get_workspace(org["id"], user_id="USR-a") is None
    with pytest.raises(PermissionError):
        pg_repo.resolve_workspace_for_user("USR-a", org["id"])
    pg_repo.join_organization(user_id="USR-a", join_code=code)
    with bootstrap_transaction(pg_repo.engine, user_id="USR-a") as connection:
        assert set(connection.execute(select(dbm.workspaces.c.id)).scalars()) == {a["id"], org["id"]}
        rows = connection.execute(select(dbm.organization_memberships)).mappings().all()
        assert len(rows) == 1 and rows[0]["user_id"] == "USR-a"


def test_live_inactive_membership_hidden_and_secret_rejoin_preserves_role(pg_repo):
    org, code = pg_repo.create_organization(creator_user_id="USR-b", name="Team")
    pg_repo.join_organization(user_id="USR-a", join_code=code)
    pg_repo.change_organization_membership_role(workspace_id=org["id"], actor_user_id="USR-b", target_user_id="USR-a", new_role="admin")
    with tenant_transaction(pg_repo.engine, workspace_id=org["id"], user_id="USR-b") as connection:
        connection.execute(update(dbm.organization_memberships).where(
            dbm.organization_memberships.c.user_id == "USR-a").values(active=False))
    with bootstrap_transaction(pg_repo.engine, user_id="USR-a") as connection:
        assert connection.execute(select(dbm.organization_memberships)).all() == []
        assert connection.execute(select(dbm.workspaces).where(dbm.workspaces.c.id == org["id"])).all() == []
    assert pg_repo.list_organization_memberships_for_user("USR-a", active_only=False) == []
    assert pg_repo.get_organization_membership(org["id"], "USR-a") is None
    code = pg_repo.manage_organization_invites(workspace_id=org["id"], user_id="USR-b", action="generate")["joinCode"]
    _, membership = pg_repo.join_organization(user_id="USR-a", join_code=code)
    assert membership["membership_role"] == "admin" and membership["active"]
    # Existing owner must not be downgraded by repeated join.
    code = pg_repo.manage_organization_invites(workspace_id=org["id"], user_id="USR-b", action="generate")["joinCode"]
    assert pg_repo.join_organization(user_id="USR-b", join_code=code)[1]["membership_role"] == "owner"


def test_live_unset_bootstrap_context_fails_closed_for_reads_and_writes(pg_repo):
    own = pg_repo.get_personal_workspace("USR-a")
    pg_repo.save_user(make_user("USR-c"))  # Valid FK, no existing Personal Workspace.
    foreign = {**own, "personal_owner_user_id": "USR-c", "created_by_user_id": "USR-c"}
    with pg_repo.engine.connect() as connection:
        assert connection.execute(select(dbm.workspaces)).all() == []
        assert connection.execute(select(dbm.organization_memberships)).all() == []
    with pytest.raises(DBAPIError):
        with pg_repo.engine.begin() as connection:
            connection.execute(insert(dbm.workspaces).values(**{**foreign, "id": "WS-unscoped"}))
    with pytest.raises(DBAPIError):
        with bootstrap_transaction(pg_repo.engine, user_id="USR-a") as connection:
            connection.execute(insert(dbm.workspaces).values(**{**foreign, "id": "WS-wrong-owner"}))


@pytest.mark.parametrize("rollback", [False, True])
def test_live_bootstrap_pool_identity_clears_on_commit_and_rollback(pg_repo, rollback):
    class Abort(Exception):
        pass
    try:
        with bootstrap_transaction(pg_repo.engine, user_id="USR-a") as connection:
            pid = connection.execute(text("SELECT pg_backend_pid()")).scalar_one()
            assert connection.execute(text(f"SELECT {CURRENT_USER_SQL}, {CURRENT_WORKSPACE_SQL}")).one() == ("USR-a", None)
            if rollback:
                raise Abort()
    except Abort:
        assert rollback
    with pg_repo.engine.connect() as connection:
        assert connection.execute(text("SELECT pg_backend_pid()")).scalar_one() == pid
        assert connection.execute(text(
            f"SELECT {CURRENT_USER_SQL}, {CURRENT_WORKSPACE_SQL}, {INVITATION_DIGEST_SQL}, {INVITATION_WORKSPACE_SQL}, {RECOVERY_OWNER_SQL}"
        )).one() == (None, None, None, None, None)
        assert connection.execute(select(dbm.workspaces)).all() == []
    with bootstrap_transaction(pg_repo.engine, user_id="USR-b") as connection:
        assert connection.execute(select(dbm.workspaces.c.personal_owner_user_id)).scalars().all() == ["USR-b"]


def test_live_selection_transitions_from_bootstrap_to_scoped_tenant(pg_repo):
    a = seed(pg_repo, "T-a", "USR-a")
    b = seed(pg_repo, "T-b", "USR-b")
    selected = pg_repo.resolve_workspace_for_user("USR-a", a.workspace_id)
    with bootstrap_transaction(pg_repo.engine, user_id="USR-a") as connection:
        assert connection.execute(select(dbm.simulations)).all() == []
        apply_tenant_session_context(connection, workspace_id=selected["id"], user_id="USR-a")
        assert connection.execute(select(dbm.simulations.c.id)).scalars().all() == [a.id]
        assert connection.execute(select(dbm.workspaces.c.id)).scalars().all() == [a.workspace_id]
        assert connection.execute(select(dbm.simulations).where(dbm.simulations.c.id == b.id)).all() == []


def test_live_invitation_capability_matches_only_secret_and_does_not_leak(pg_repo):
    org, code = pg_repo.create_organization(creator_user_id="USR-b", name="Team")
    another, _ = pg_repo.create_organization(creator_user_id="USR-b", name="Another")
    with invitation_transaction(pg_repo.engine, user_id="USR-a", digest=join_code_digest(code)) as connection:
        visible = set(connection.execute(select(dbm.workspaces.c.id)).scalars())
        assert org["id"] in visible and another["id"] not in visible
        assert connection.execute(select(dbm.organization_memberships)).all() == []
    with pg_repo.engine.connect() as connection:
        assert connection.execute(text(f"SELECT {INVITATION_DIGEST_SQL}, {INVITATION_WORKSPACE_SQL}")).one() == (None, None)
    with pytest.raises(LookupError, match="Invalid organization join code"):
        pg_repo.join_organization(user_id="USR-a", join_code="INVALID-CODE")
    assert pg_repo.get_workspace(org["id"], user_id="USR-a") is None


def test_live_selected_workspace_membership_scope_and_iam_preserved(pg_repo):
    org, code = pg_repo.create_organization(creator_user_id="USR-b", name="Team")
    pg_repo.join_organization(user_id="USR-a", join_code=code)
    second, _ = pg_repo.create_organization(creator_user_id="USR-a", name="Separate")
    with tenant_transaction(pg_repo.engine, workspace_id=org["id"], user_id="USR-a") as connection:
        assert {r["workspace_id"] for r in connection.execute(select(dbm.organization_memberships)).mappings()} == {org["id"]}
    assert resolve_workspace_authorization(pg_repo, user_id="USR-a", workspace_id=org["id"]).role == WorkspaceRole.MEMBER
    with pytest.raises(AuthorizationError):
        pg_repo.change_organization_membership_role(workspace_id=org["id"], actor_user_id="USR-a", target_user_id="USR-a", new_role="owner")
    pg_repo.change_organization_membership_role(workspace_id=org["id"], actor_user_id="USR-b", target_user_id="USR-a", new_role="admin")
    assert resolve_workspace_authorization(pg_repo, user_id="USR-a", workspace_id=org["id"]).role == WorkspaceRole.ADMIN
    assert len(pg_repo.list_organization_memberships(org["id"], actor_user_id="USR-b")) == 2
    assert pg_repo.get_organization_membership(second["id"], "USR-a")["membership_role"] == "owner"
    with pytest.raises(ValueError, match="last active"):
        pg_repo.change_organization_membership_role(workspace_id=second["id"], actor_user_id="USR-a", target_user_id="USR-a", new_role="member")


def test_live_discovery_has_no_membership_write_privilege(pg_repo):
    org, code = pg_repo.create_organization(creator_user_id="USR-b", name="Team")
    pg_repo.join_organization(user_id="USR-a", join_code=code)
    with pytest.raises(DBAPIError):
        with bootstrap_transaction(pg_repo.engine, user_id="USR-a") as connection:
            connection.execute(update(dbm.organization_memberships).where(
                dbm.organization_memberships.c.workspace_id == org["id"],
                dbm.organization_memberships.c.user_id == "USR-a",
            ).values(membership_role="owner"))
    assert pg_repo.get_organization_membership(org["id"], "USR-a")["membership_role"] == "member"


def test_live_recovery_finds_inactive_orphan_organization_without_global_bypass(pg_repo):
    org, _ = pg_repo.create_organization(creator_user_id="USR-b", name="Orphan")
    task = example_task(datetime.now(timezone.utc))
    task.id = task.simulation_id = "T-orphan"
    task.workspace_id = org["id"]
    task.status = TaskStatus.IN_PROGRESS
    for upload in task.uploads:
        pg_repo.save_upload_for_tenant(
            upload,
            workspace_id=org["id"],
            user_id="USR-b",
        )
    pg_repo.save_for_tenant(task, workspace_id=org["id"], user_id="USR-b")
    with tenant_transaction(pg_repo.engine, workspace_id=org["id"], user_id="USR-b") as connection:
        connection.execute(update(dbm.workspaces).where(dbm.workspaces.c.id == org["id"]).values(active=False))
        connection.execute(update(dbm.organization_memberships).where(dbm.organization_memberships.c.workspace_id == org["id"]).values(active=False))
    # Identity catalog must include inactive creators, not only logged-in users.
    user = pg_repo.get_user("USR-b")
    pg_repo.save_user({**user, "active": False})
    with bootstrap_transaction(pg_repo.engine, user_id="USR-a") as connection:
        assert connection.execute(select(dbm.workspaces).where(dbm.workspaces.c.id == org["id"])).all() == []
    with recovery_catalog_transaction(pg_repo.engine, owner_user_id="USR-a") as connection:
        assert connection.execute(select(dbm.workspaces).where(dbm.workspaces.c.id == org["id"])).all() == []
    assert pg_repo.recover_interrupted_tasks(_mark_interrupted_failed) == 1
    assert pg_repo.recover_interrupted_tasks(_mark_interrupted_failed) == 0
    assert pg_repo.get_for_tenant(task.id, workspace_id=org["id"], user_id="system:startup-recovery").status == TaskStatus.FAILED
