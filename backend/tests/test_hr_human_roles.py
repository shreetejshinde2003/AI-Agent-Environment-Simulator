"""Phase 4.4.1 HR-domain human-role semantics and persistence tests."""

import sqlite3
from datetime import datetime, timezone

import pytest
from sqlalchemy import insert, select

from app.security.hr_roles import (
    HRHumanPermission,
    HRHumanRole,
    ROLE_PERMISSIONS,
    resolve_hr_human_authorization,
)
from app.security.rbac import AuthorizationError
from app.storage import models as dbm
from app.storage.database import Repository, SCHEMA_VERSION


def now_text():
    return datetime.now(timezone.utc).isoformat()


def make_user(user_id: str):
    now = now_text()
    return {
        "id": user_id,
        "google_sub": f"google-{user_id}",
        "email": f"{user_id.lower()}@example.com",
        "display_name": user_id,
        "profile_picture": None,
        "email_verified": True,
        "active": True,
        "created_at": now,
        "last_login_at": now,
    }


def seed_org(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'hr-human-roles.db'}")
    repo.initialize()
    for user_id in ("owner", "admin", "member", "outsider"):
        repo.save_user(make_user(user_id))

    workspace, _ = repo.create_organization(
        creator_user_id="owner",
        name="IICT",
    )
    repo.save_organization_membership(
        {
            "workspace_id": workspace["id"],
            "user_id": "admin",
            "membership_role": "admin",
            "active": True,
            "joined_at": now_text(),
            "added_by_user_id": "owner",
        }
    )
    repo.save_organization_membership(
        {
            "workspace_id": workspace["id"],
            "user_id": "member",
            "membership_role": "member",
            "active": True,
            "joined_at": now_text(),
            "added_by_user_id": "owner",
        }
    )
    return repo, workspace


def test_fresh_v10_database_contains_hr_human_role_table(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'fresh-v8.db'}")
    repo.initialize()

    with repo.engine.connect() as connection:
        names = set(connection.dialect.get_table_names(connection))
        version = connection.execute(select(dbm.schema_version.c.version)).scalar_one()

    assert "organization_human_role_assignments" in names
    assert version == SCHEMA_VERSION == 12

    with sqlite3.connect(repo.path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 12


def test_v7_database_migrates_additively_to_v10(tmp_path):
    path = tmp_path / "v7.db"
    repo = Repository(f"sqlite:///{path}")

    with repo.engine.begin() as connection:
        for table in dbm.metadata.sorted_tables:
            if table.name != "organization_human_role_assignments":
                table.create(connection, checkfirst=True)
        connection.execute(
            insert(dbm.schema_version).values(
                version=7,
                applied_at=now_text(),
            )
        )

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=7")

    repo.initialize()

    with repo.engine.connect() as connection:
        names = set(connection.dialect.get_table_names(connection))
        version = connection.execute(select(dbm.schema_version.c.version)).scalar_one()

    assert "organization_human_role_assignments" in names
    assert version == 12


def test_hr_human_role_capability_matrix_is_separate_and_explicit():
    recruiter = ROLE_PERMISSIONS[HRHumanRole.RECRUITER]
    reviewer = ROLE_PERMISSIONS[HRHumanRole.REVIEWER]
    approver = ROLE_PERMISSIONS[HRHumanRole.APPROVER]

    assert HRHumanPermission.HIRING_REQUEST_MANAGE in recruiter
    assert HRHumanPermission.JD_DRAFT_EDIT in recruiter
    assert HRHumanPermission.JD_APPROVE not in recruiter

    assert HRHumanPermission.JD_REVIEW in reviewer
    assert HRHumanPermission.JD_REQUEST_REVISION in reviewer
    assert HRHumanPermission.JD_APPROVE not in reviewer

    assert HRHumanPermission.JD_APPROVE in approver
    assert HRHumanPermission.JD_REJECT in approver
    assert HRHumanPermission.JD_DRAFT_EDIT not in approver


def test_owner_and_admin_can_assign_roles_but_member_and_outsider_cannot(tmp_path):
    repo, workspace = seed_org(tmp_path)

    recruiter = repo.assign_organization_human_role(
        workspace_id=workspace["id"],
        actor_user_id="owner",
        target_user_id="member",
        human_role="hr_recruiter",
    )
    reviewer = repo.assign_organization_human_role(
        workspace_id=workspace["id"],
        actor_user_id="admin",
        target_user_id="member",
        human_role="hr_reviewer",
    )

    assert recruiter["human_role"] == "hr_recruiter"
    assert reviewer["human_role"] == "hr_reviewer"

    for actor_id in ("member", "outsider"):
        with pytest.raises(AuthorizationError):
            repo.assign_organization_human_role(
                workspace_id=workspace["id"],
                actor_user_id=actor_id,
                target_user_id="member",
                human_role="hr_approver",
            )


def test_one_member_can_hold_multiple_hr_human_roles(tmp_path):
    repo, workspace = seed_org(tmp_path)

    for role in ("hr_recruiter", "hr_reviewer", "hr_approver"):
        repo.assign_organization_human_role(
            workspace_id=workspace["id"],
            actor_user_id="owner",
            target_user_id="member",
            human_role=role,
        )

    assignments = repo.list_organization_human_roles(
        workspace["id"],
        user_id="member",
    )

    assert {row["human_role"] for row in assignments} == {
        "hr_recruiter",
        "hr_reviewer",
        "hr_approver",
    }


def test_deactivation_preserves_assignment_but_removes_active_capability(tmp_path):
    repo, workspace = seed_org(tmp_path)
    repo.assign_organization_human_role(
        workspace_id=workspace["id"],
        actor_user_id="owner",
        target_user_id="member",
        human_role="hr_approver",
    )

    before = resolve_hr_human_authorization(
        repo,
        user_id="member",
        workspace_id=workspace["id"],
    )
    assert before.allows(HRHumanPermission.JD_APPROVE)

    deactivated = repo.deactivate_organization_human_role(
        workspace_id=workspace["id"],
        actor_user_id="admin",
        target_user_id="member",
        human_role="hr_approver",
    )
    assert deactivated["active"] is False
    assert repo.list_organization_human_roles(
        workspace["id"], user_id="member"
    ) == []
    assert len(
        repo.list_organization_human_roles(
            workspace["id"], user_id="member", active_only=False
        )
    ) == 1

    after = resolve_hr_human_authorization(
        repo,
        user_id="member",
        workspace_id=workspace["id"],
    )
    assert not after.allows(HRHumanPermission.JD_APPROVE)


def test_personal_workspace_and_inactive_member_cannot_receive_hr_roles(tmp_path):
    repo, workspace = seed_org(tmp_path)
    personal = repo.ensure_personal_workspace("owner")

    with pytest.raises(AuthorizationError):
        repo.assign_organization_human_role(
            workspace_id=personal["id"],
            actor_user_id="owner",
            target_user_id="owner",
            human_role="hr_recruiter",
        )

    membership = repo.get_organization_membership(workspace["id"], "member")
    membership["active"] = False
    repo.save_organization_membership(membership)

    with pytest.raises(AuthorizationError):
        repo.assign_organization_human_role(
            workspace_id=workspace["id"],
            actor_user_id="owner",
            target_user_id="member",
            human_role="hr_recruiter",
        )


def test_inactive_membership_invalidates_existing_hr_roles(tmp_path):
    repo, workspace = seed_org(tmp_path)
    repo.assign_organization_human_role(
        workspace_id=workspace["id"],
        actor_user_id="owner",
        target_user_id="member",
        human_role="hr_reviewer",
    )

    membership = repo.get_organization_membership(workspace["id"], "member")
    membership["active"] = False
    repo.save_organization_membership(membership)

    authorization = resolve_hr_human_authorization(
        repo,
        user_id="member",
        workspace_id=workspace["id"],
    )
    assert authorization.roles == frozenset()
    assert not authorization.allows(HRHumanPermission.JD_REVIEW)


def test_unknown_hr_role_is_rejected(tmp_path):
    repo, workspace = seed_org(tmp_path)
    with pytest.raises(ValueError, match="Unsupported HR human role"):
        repo.assign_organization_human_role(
            workspace_id=workspace["id"],
            actor_user_id="owner",
            target_user_id="member",
            human_role="hr_superuser",
        )
