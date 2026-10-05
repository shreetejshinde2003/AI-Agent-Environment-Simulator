"""Phase 4.3.2 persisted organization roles and safe role-management tests."""

import sqlite3
from datetime import datetime, timezone

import pytest
from sqlalchemy import insert, select

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


def make_workspace(owner_id: str, workspace_id: str = "WS-iict"):
    now = now_text()
    return {
        "id": workspace_id,
        "kind": "organization",
        "name": "IICT",
        "personal_owner_user_id": None,
        "created_by_user_id": owner_id,
        "join_code_digest": None,
        "active": True,
        "created_at": now,
        "updated_at": now,
    }


def membership(workspace_id: str, user_id: str, role: str, added_by: str, *, active=True):
    return {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "membership_role": role,
        "active": active,
        "joined_at": now_text(),
        "added_by_user_id": added_by,
    }


def seeded_repo(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'roles.db'}")
    repo.initialize()

    owner = make_user("USR-owner")
    admin = make_user("USR-admin")
    member = make_user("USR-member")
    outsider = make_user("USR-outsider")

    for user in (owner, admin, member, outsider):
        repo.save_user(user)

    workspace = make_workspace(owner["id"])
    repo.save_workspace(workspace)

    repo.save_organization_membership(
        membership(workspace["id"], owner["id"], "owner", owner["id"])
    )
    repo.save_organization_membership(
        membership(workspace["id"], admin["id"], "admin", owner["id"])
    )
    repo.save_organization_membership(
        membership(workspace["id"], member["id"], "member", owner["id"])
    )

    return repo, workspace, owner, admin, member, outsider


def test_fresh_v9_database_persists_admin_role(tmp_path):
    repo, workspace, owner, admin, _, _ = seeded_repo(tmp_path)

    restored = repo.get_organization_membership(workspace["id"], admin["id"])
    assert restored["membership_role"] == "admin"

    with sqlite3.connect(repo.path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION == 9


def test_v6_membership_constraint_migrates_to_v8_and_preserves_rows(tmp_path):
    path = tmp_path / "v6.db"
    repo = Repository(f"sqlite:///{path}")

    with repo.engine.begin() as connection:
        for table in dbm.metadata.sorted_tables:
            if table.name != "organization_memberships":
                table.create(connection, checkfirst=True)

        connection.exec_driver_sql(
            "CREATE TABLE organization_memberships ("
            "workspace_id VARCHAR(80) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE, "
            "user_id VARCHAR(80) NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
            "membership_role VARCHAR(20) NOT NULL, "
            "active BOOLEAN NOT NULL, "
            "joined_at VARCHAR(40) NOT NULL, "
            "added_by_user_id VARCHAR(80) NOT NULL REFERENCES users(id) ON DELETE RESTRICT, "
            "PRIMARY KEY (workspace_id, user_id), "
            "CONSTRAINT ck_organization_membership_role "
            "CHECK (membership_role IN ('owner', 'member'))"
            ")"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_org_memberships_user_active "
            "ON organization_memberships (user_id, active)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_org_memberships_workspace_active "
            "ON organization_memberships (workspace_id, active)"
        )

        owner = make_user("USR-owner")
        member = make_user("USR-member")
        connection.execute(insert(dbm.users), [owner, member])
        workspace = make_workspace(owner["id"])
        connection.execute(insert(dbm.workspaces).values(**workspace))
        connection.exec_driver_sql(
            "INSERT INTO organization_memberships "
            "(workspace_id, user_id, membership_role, active, joined_at, added_by_user_id) "
            "VALUES (?, ?, 'owner', 1, ?, ?), (?, ?, 'member', 1, ?, ?)",
            (
                workspace["id"], owner["id"], now_text(), owner["id"],
                workspace["id"], member["id"], now_text(), owner["id"],
            ),
        )
        connection.execute(insert(dbm.schema_version).values(version=6, applied_at=now_text()))

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=6")

    repo.initialize()

    assert repo.get_organization_membership(workspace["id"], owner["id"])["membership_role"] == "owner"
    assert repo.get_organization_membership(workspace["id"], member["id"])["membership_role"] == "member"

    repo.change_organization_membership_role(
        workspace_id=workspace["id"],
        actor_user_id=owner["id"],
        target_user_id=member["id"],
        new_role="admin",
    )
    assert repo.get_organization_membership(workspace["id"], member["id"])["membership_role"] == "admin"


def test_owner_can_promote_member_to_admin_and_demote_admin(tmp_path):
    repo, workspace, owner, admin, member, _ = seeded_repo(tmp_path)

    promoted = repo.change_organization_membership_role(
        workspace_id=workspace["id"],
        actor_user_id=owner["id"],
        target_user_id=member["id"],
        new_role="admin",
    )
    assert promoted["membership_role"] == "admin"

    demoted = repo.change_organization_membership_role(
        workspace_id=workspace["id"],
        actor_user_id=owner["id"],
        target_user_id=admin["id"],
        new_role="member",
    )
    assert demoted["membership_role"] == "member"


def test_admin_cannot_promote_members_or_change_admin_roles(tmp_path):
    repo, workspace, _, admin, member, _ = seeded_repo(tmp_path)

    with pytest.raises(AuthorizationError):
        repo.change_organization_membership_role(
            workspace_id=workspace["id"],
            actor_user_id=admin["id"],
            target_user_id=member["id"],
            new_role="admin",
        )

    with pytest.raises(AuthorizationError):
        repo.change_organization_membership_role(
            workspace_id=workspace["id"],
            actor_user_id=admin["id"],
            target_user_id=admin["id"],
            new_role="member",
        )


def test_member_and_outsider_cannot_change_roles(tmp_path):
    repo, workspace, _, _, member, outsider = seeded_repo(tmp_path)

    for actor_id in (member["id"], outsider["id"]):
        with pytest.raises(AuthorizationError):
            repo.change_organization_membership_role(
                workspace_id=workspace["id"],
                actor_user_id=actor_id,
                target_user_id=member["id"],
                new_role="admin",
            )


def test_inactive_target_cannot_be_promoted(tmp_path):
    repo, workspace, owner, _, member, _ = seeded_repo(tmp_path)
    stored = repo.get_organization_membership(workspace["id"], member["id"])
    stored["active"] = False
    repo.save_organization_membership(stored)

    with pytest.raises(AuthorizationError):
        repo.change_organization_membership_role(
            workspace_id=workspace["id"],
            actor_user_id=owner["id"],
            target_user_id=member["id"],
            new_role="admin",
        )


def test_last_active_owner_cannot_be_demoted(tmp_path):
    repo, workspace, owner, _, _, _ = seeded_repo(tmp_path)

    with pytest.raises(ValueError, match="last active organization owner"):
        repo.change_organization_membership_role(
            workspace_id=workspace["id"],
            actor_user_id=owner["id"],
            target_user_id=owner["id"],
            new_role="admin",
        )


def test_owner_can_add_second_owner_then_demote_self(tmp_path):
    repo, workspace, owner, _, member, _ = seeded_repo(tmp_path)

    repo.change_organization_membership_role(
        workspace_id=workspace["id"],
        actor_user_id=owner["id"],
        target_user_id=member["id"],
        new_role="owner",
    )

    demoted = repo.change_organization_membership_role(
        workspace_id=workspace["id"],
        actor_user_id=owner["id"],
        target_user_id=owner["id"],
        new_role="admin",
    )

    assert demoted["membership_role"] == "admin"
    assert repo.get_organization_membership(workspace["id"], member["id"])["membership_role"] == "owner"


def test_role_change_is_scoped_to_one_organization(tmp_path):
    repo, workspace, owner, _, member, outsider = seeded_repo(tmp_path)

    other = make_workspace(outsider["id"], "WS-other")
    repo.save_workspace(other)
    repo.save_organization_membership(
        membership(other["id"], outsider["id"], "owner", outsider["id"])
    )
    repo.save_organization_membership(
        membership(other["id"], member["id"], "member", outsider["id"])
    )

    with pytest.raises(AuthorizationError):
        repo.change_organization_membership_role(
            workspace_id=other["id"],
            actor_user_id=owner["id"],
            target_user_id=member["id"],
            new_role="admin",
        )

    assert repo.get_organization_membership(other["id"], member["id"])["membership_role"] == "member"
    assert repo.get_organization_membership(workspace["id"], member["id"])["membership_role"] == "member"
