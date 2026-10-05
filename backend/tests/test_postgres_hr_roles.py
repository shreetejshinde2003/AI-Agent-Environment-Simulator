"""Opt-in HR-role FORCE RLS enforcement on an isolated local PostgreSQL schema.

Requires TENANT_TEST_DATABASE_URL via the existing non-bypass, one-connection
fixture. Skipped cases are NOT enforcement proof. No production DB/provider use.
"""

import pytest
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.exc import DBAPIError

from app.security.hr_roles import HRHumanPermission, resolve_hr_human_authorization
from app.security.postgres_rls import POLICY_NAME, WRITE_POLICY_NAME
from app.security.rbac import AuthorizationError, resolve_workspace_authorization
from app.security.tenant_db_context import (
    bootstrap_transaction, tenant_transaction, CURRENT_USER_SQL,
    CURRENT_WORKSPACE_SQL, INVITATION_DIGEST_SQL, INVITATION_WORKSPACE_SQL,
    RECOVERY_OWNER_SQL,
)
from app.storage import models as dbm
from test_postgres_data_plane_integration import pg_repo
from test_tenant_repository_primitives import make_user


@pytest.fixture
def hr_orgs(pg_repo):
    for uid in ("USR-admin", "USR-other"):
        pg_repo.save_user(make_user(uid))
    a, code_a = pg_repo.create_organization(creator_user_id="USR-b", name="HR Organization A")
    b, code_b = pg_repo.create_organization(creator_user_id="USR-other", name="HR Organization B")
    for uid in ("USR-a", "USR-admin"):
        pg_repo.join_organization(user_id=uid, join_code=code_a)
    pg_repo.join_organization(user_id="USR-a", join_code=code_b)
    pg_repo.change_organization_membership_role(workspace_id=a["id"], actor_user_id="USR-b", target_user_id="USR-admin", new_role="admin")
    assignment = pg_repo.assign_organization_human_role(workspace_id=a["id"], actor_user_id="USR-b", target_user_id="USR-a", human_role="hr_approver")
    pg_repo.assign_organization_human_role(workspace_id=a["id"], actor_user_id="USR-b", target_user_id="USR-admin", human_role="hr_reviewer")
    pg_repo.assign_organization_human_role(workspace_id=b["id"], actor_user_id="USR-other", target_user_id="USR-a", human_role="hr_recruiter")
    return pg_repo, a["id"], b["id"], assignment


def test_live_hr_enable_force_and_distinct_read_write_policies(hr_orgs):
    repo, _, _, _ = hr_orgs
    repo.initialize()
    with repo.engine.connect() as connection:
        assert connection.execute(text(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE oid = to_regclass('organization_human_role_assignments')"
        )).one() == (True, True)
        names = dict(connection.execute(text(
            "SELECT polname, polcmd FROM pg_policy WHERE polrelid = to_regclass('organization_human_role_assignments')"
        )).all())
        assert names == {POLICY_NAME: "r", WRITE_POLICY_NAME: "*"}


def test_live_hr_cross_org_and_missing_context_filter_unrestricted_selects(hr_orgs):
    repo, a, b, _ = hr_orgs
    table = dbm.organization_human_role_assignments
    with repo.engine.connect() as connection:
        assert connection.execute(select(table)).all() == []
    with bootstrap_transaction(repo.engine, user_id="USR-b") as connection:
        assert connection.execute(select(table)).all() == []
    with repo.engine.begin() as connection:
        connection.execute(text("SELECT set_config('app.current_workspace_id', :ws, true)"), {"ws": a})
        assert connection.execute(select(table)).all() == []
    with tenant_transaction(repo.engine, workspace_id=a, user_id="USR-b") as connection:
        assert {row["workspace_id"] for row in connection.execute(select(table)).mappings()} == {a}
        assert connection.execute(delete(table).where(table.c.workspace_id == b)).rowcount == 0
    # Even a wrongly selected foreign workspace cannot create IAM membership.
    with tenant_transaction(repo.engine, workspace_id=b, user_id="USR-b") as connection:
        assert connection.execute(select(table)).all() == []
    with tenant_transaction(repo.engine, workspace_id=a, user_id="USR-a") as connection:
        assert [row["user_id"] for row in connection.execute(select(table)).mappings()] == ["USR-a"]
    roles_a = resolve_hr_human_authorization(repo, user_id="USR-a", workspace_id=a)
    roles_b = resolve_hr_human_authorization(repo, user_id="USR-a", workspace_id=b)
    assert roles_a.allows(HRHumanPermission.JD_APPROVE)
    assert not roles_b.allows(HRHumanPermission.JD_APPROVE)
    assert roles_b.allows(HRHumanPermission.JD_DRAFT_EDIT)


def test_live_member_cannot_insert_update_delete_or_self_promote(hr_orgs):
    repo, a, _, assignment = hr_orgs
    table = dbm.organization_human_role_assignments
    with pytest.raises(AuthorizationError):
        repo.assign_organization_human_role(workspace_id=a, actor_user_id="USR-a", target_user_id="USR-a", human_role="hr_reviewer")
    with tenant_transaction(repo.engine, workspace_id=a, user_id="USR-a") as connection:
        assert connection.execute(update(table).values(active=False)).rowcount == 0
        assert connection.execute(delete(table)).rowcount == 0
    with pytest.raises(DBAPIError):
        with tenant_transaction(repo.engine, workspace_id=a, user_id="USR-a") as connection:
            connection.execute(insert(table).values(**{**assignment, "human_role": "hr_reviewer", "assigned_by_user_id": "USR-a"}))
    assert resolve_hr_human_authorization(repo, user_id="USR-a", workspace_id=a).allows(HRHumanPermission.JD_APPROVE)


def test_live_admin_manage_domain_not_iam_and_no_cross_org_or_actor_forgery(hr_orgs):
    repo, a, b, assignment = hr_orgs
    repo.assign_organization_human_role(workspace_id=a, actor_user_id="USR-admin", target_user_id="USR-b", human_role="hr_recruiter")
    assert len(repo.list_organization_human_roles(a, actor_user_id="USR-admin")) == 3
    with pytest.raises(AuthorizationError):
        repo.change_organization_membership_role(workspace_id=a, actor_user_id="USR-admin", target_user_id="USR-a", new_role="owner")
    with pytest.raises(AuthorizationError):
        repo.assign_organization_human_role(workspace_id=b, actor_user_id="USR-admin", target_user_id="USR-a", human_role="hr_reviewer")
    with pytest.raises(DBAPIError):
        with tenant_transaction(repo.engine, workspace_id=a, user_id="USR-admin") as connection:
            connection.execute(insert(dbm.organization_human_role_assignments).values(
                **{**assignment, "human_role": "hr_reviewer", "assigned_by_user_id": "USR-a"}
            ))
    with pytest.raises(DBAPIError):
        with tenant_transaction(repo.engine, workspace_id=a, user_id="USR-b") as connection:
            connection.execute(update(dbm.organization_human_role_assignments).where(
                dbm.organization_human_role_assignments.c.user_id == "USR-a"
            ).values(workspace_id=b))


def test_live_membership_and_assignment_revocation_are_immediate(hr_orgs):
    repo, a, _, _ = hr_orgs
    repo.deactivate_organization_human_role(workspace_id=a, actor_user_id="USR-admin", target_user_id="USR-a", human_role="hr_approver")
    assert not resolve_hr_human_authorization(repo, user_id="USR-a", workspace_id=a).roles
    assert repo.list_organization_human_roles(a, user_id="USR-a", actor_user_id="USR-admin", active_only=False)[0]["active"] is False
    repo.assign_organization_human_role(workspace_id=a, actor_user_id="USR-admin", target_user_id="USR-a", human_role="hr_approver")
    with tenant_transaction(repo.engine, workspace_id=a, user_id="USR-b") as connection:
        connection.execute(update(dbm.organization_memberships).where(
            dbm.organization_memberships.c.user_id == "USR-a", dbm.organization_memberships.c.workspace_id == a,
        ).values(active=False))
    assert not resolve_hr_human_authorization(repo, user_id="USR-a", workspace_id=a).roles
    with tenant_transaction(repo.engine, workspace_id=a, user_id="USR-a") as connection:
        assert connection.execute(select(dbm.organization_human_role_assignments)).all() == []
    with pytest.raises(AuthorizationError):
        repo.assign_organization_human_role(workspace_id=a, actor_user_id="USR-admin", target_user_id="USR-a", human_role="hr_recruiter")
    # Deactivation of existing history remains possible after target membership loss.
    assert repo.deactivate_organization_human_role(workspace_id=a, actor_user_id="USR-admin", target_user_id="USR-a", human_role="hr_approver")["active"] is False
    with tenant_transaction(repo.engine, workspace_id=a, user_id="USR-b") as connection:
        connection.execute(update(dbm.organization_memberships).where(
            dbm.organization_memberships.c.user_id == "USR-admin", dbm.organization_memberships.c.workspace_id == a,
        ).values(active=False))
    with pytest.raises(AuthorizationError):
        repo.list_organization_human_roles(a, actor_user_id="USR-admin")


def test_live_personal_hr_role_insert_and_authorization_fail_closed(hr_orgs):
    repo, _, _, assignment = hr_orgs
    personal = repo.get_personal_workspace("USR-b")["id"]
    assert not resolve_hr_human_authorization(repo, user_id="USR-b", workspace_id=personal).roles
    with pytest.raises(DBAPIError):
        with tenant_transaction(repo.engine, workspace_id=personal, user_id="USR-b") as connection:
            connection.execute(insert(dbm.organization_human_role_assignments).values(**{**assignment, "workspace_id": personal}))


@pytest.mark.parametrize("rollback", [False, True])
def test_live_hr_context_does_not_leak_to_same_pooled_connection(hr_orgs, rollback):
    repo, a, _, _ = hr_orgs
    class Abort(Exception):
        pass
    try:
        with tenant_transaction(repo.engine, workspace_id=a, user_id="USR-b") as connection:
            pid = connection.execute(text("SELECT pg_backend_pid()")).scalar_one()
            assert connection.execute(select(dbm.organization_human_role_assignments)).all()
            if rollback:
                raise Abort()
    except Abort:
        assert rollback
    with repo.engine.connect() as connection:
        assert connection.execute(text("SELECT pg_backend_pid()")).scalar_one() == pid
        assert connection.execute(text(
            f"SELECT {CURRENT_WORKSPACE_SQL}, {CURRENT_USER_SQL}, {INVITATION_DIGEST_SQL}, {INVITATION_WORKSPACE_SQL}, {RECOVERY_OWNER_SQL}"
        )).one() == (None, None, None, None, None)
        assert connection.execute(select(dbm.organization_human_role_assignments)).all() == []


def test_live_rolled_back_hr_deactivation_preserves_saved_permission(hr_orgs):
    repo, a, _, _ = hr_orgs
    class Abort(Exception):
        pass
    with pytest.raises(Abort):
        with tenant_transaction(repo.engine, workspace_id=a, user_id="USR-b") as connection:
            connection.execute(update(dbm.organization_human_role_assignments).where(
                dbm.organization_human_role_assignments.c.user_id == "USR-a"
            ).values(active=False, assigned_by_user_id="USR-b"))
            raise Abort()
    assert resolve_hr_human_authorization(repo, user_id="USR-a", workspace_id=a).allows(HRHumanPermission.JD_APPROVE)

def test_live_member_removal_deactivates_membership_and_hr_roles_atomically(hr_orgs):
    repo, a, _, _ = hr_orgs

    removed = repo.deactivate_organization_membership(
        workspace_id=a,
        actor_user_id="USR-b",
        target_user_id="USR-a",
    )

    assert removed["active"] is False

    with tenant_transaction(
        repo.engine,
        workspace_id=a,
        user_id="USR-b",
    ) as connection:
        membership = connection.execute(
            select(dbm.organization_memberships).where(
                dbm.organization_memberships.c.workspace_id == a,
                dbm.organization_memberships.c.user_id == "USR-a",
            )
        ).mappings().one()

        assignments = connection.execute(
            select(dbm.organization_human_role_assignments).where(
                dbm.organization_human_role_assignments.c.workspace_id == a,
                dbm.organization_human_role_assignments.c.user_id == "USR-a",
            )
        ).mappings().all()

    assert membership["active"] is False
    assert assignments
    assert all(row["active"] is False for row in assignments)
    assert all(row["assigned_by_user_id"] == "USR-b" for row in assignments)

    with pytest.raises(AuthorizationError):
        resolve_workspace_authorization(
            repo,
            user_id="USR-a",
            workspace_id=a,
        )

    assert not resolve_hr_human_authorization(
        repo,
        user_id="USR-a",
        workspace_id=a,
    ).roles


def test_live_admin_member_removal_obeys_iam_boundary(hr_orgs):
    repo, a, _, _ = hr_orgs

    removed = repo.deactivate_organization_membership(
        workspace_id=a,
        actor_user_id="USR-admin",
        target_user_id="USR-a",
    )
    assert removed["active"] is False

    with pytest.raises(AuthorizationError):
        repo.deactivate_organization_membership(
            workspace_id=a,
            actor_user_id="USR-admin",
            target_user_id="USR-admin",
        )

    with pytest.raises(AuthorizationError):
        repo.deactivate_organization_membership(
            workspace_id=a,
            actor_user_id="USR-admin",
            target_user_id="USR-b",
        )
