"""Phase 4.2.2 organization-membership persistence tests."""

import sqlite3
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, insert, select
from sqlalchemy.exc import IntegrityError

from app.storage import models as dbm
from app.storage.database import Repository, SCHEMA_VERSION


def now_text():
    return datetime.now(timezone.utc).isoformat()


def make_user(
    user_id: str,
    google_sub: str,
):
    now = now_text()

    return {
        "id": user_id,
        "google_sub": google_sub,
        "email": f"{user_id.lower()}@example.com",
        "display_name": user_id,
        "profile_picture": None,
        "email_verified": True,
        "active": True,
        "created_at": now,
        "last_login_at": now,
    }


def make_organization(
    creator_id: str,
    workspace_id: str = "WS-org-a",
):
    now = now_text()

    return {
        "id": workspace_id,
        "kind": "organization",
        "name": "Example Organization",
        "personal_owner_user_id": None,
        "created_by_user_id": creator_id,
        "join_code_digest": None,
        "active": True,
        "created_at": now,
        "updated_at": now,
    }


def make_personal_workspace(
    owner_id: str,
):
    now = now_text()

    return {
        "id": "WS-personal-a",
        "kind": "personal",
        "name": "Personal Workspace",
        "personal_owner_user_id": owner_id,
        "created_by_user_id": owner_id,
        "join_code_digest": None,
        "active": True,
        "created_at": now,
        "updated_at": now,
    }


def make_membership(
    workspace_id: str,
    user_id: str,
    *,
    role: str = "member",
    added_by: str,
):
    return {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "membership_role": role,
        "active": True,
        "joined_at": now_text(),
        "added_by_user_id": added_by,
    }


def test_fresh_v10_database_contains_membership_table(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'membership.db'}"
    )

    repo.initialize()

    names = set(
        inspect(repo.engine).get_table_names()
    )

    assert "organization_memberships" in names

    with sqlite3.connect(repo.path) as connection:
        assert (
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
            == SCHEMA_VERSION
            == 13
        )


def test_owner_membership_round_trip(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'owner.db'}"
    )
    repo.initialize()

    owner = make_user(
        "USR-owner",
        "google-owner",
    )

    repo.save_user(owner)

    organization = make_organization(
        owner["id"]
    )

    repo.save_workspace(organization)

    membership = make_membership(
        organization["id"],
        owner["id"],
        role="owner",
        added_by=owner["id"],
    )

    repo.save_organization_membership(
        membership
    )

    restored = (
        repo.get_organization_membership(
            organization["id"],
            owner["id"],
        )
    )

    assert restored["membership_role"] == "owner"
    assert restored["active"] is True


def test_member_can_belong_to_same_organization(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'members.db'}"
    )
    repo.initialize()

    owner = make_user(
        "USR-owner",
        "google-owner",
    )

    member = make_user(
        "USR-member",
        "google-member",
    )

    repo.save_user(owner)
    repo.save_user(member)

    organization = make_organization(
        owner["id"]
    )

    repo.save_workspace(organization)

    repo.save_organization_membership(
        make_membership(
            organization["id"],
            owner["id"],
            role="owner",
            added_by=owner["id"],
        )
    )

    repo.save_organization_membership(
        make_membership(
            organization["id"],
            member["id"],
            role="member",
            added_by=owner["id"],
        )
    )

    memberships = (
        repo.list_organization_memberships(
            organization["id"]
        )
    )

    assert {
        item["user_id"]
        for item in memberships
    } == {
        owner["id"],
        member["id"],
    }


def test_user_can_belong_to_multiple_organizations(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'multi-org.db'}"
    )
    repo.initialize()

    user = make_user(
        "USR-user",
        "google-user",
    )

    repo.save_user(user)

    first = make_organization(
        user["id"],
        "WS-org-a",
    )

    second = make_organization(
        user["id"],
        "WS-org-b",
    )

    repo.save_workspace(first)
    repo.save_workspace(second)

    for organization in (
        first,
        second,
    ):
        repo.save_organization_membership(
            make_membership(
                organization["id"],
                user["id"],
                role="owner",
                added_by=user["id"],
            )
        )

    memberships = (
        repo.list_organization_memberships_for_user(
            user["id"]
        )
    )

    assert {
        item["workspace_id"]
        for item in memberships
    } == {
        first["id"],
        second["id"],
    }


def test_personal_workspace_rejects_membership(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'personal-reject.db'}"
    )
    repo.initialize()

    user = make_user(
        "USR-user",
        "google-user",
    )

    repo.save_user(user)

    personal = make_personal_workspace(
        user["id"]
    )

    repo.save_workspace(personal)

    with pytest.raises(
        ValueError,
        match="Personal Workspaces",
    ):
        repo.save_organization_membership(
            make_membership(
                personal["id"],
                user["id"],
                role="owner",
                added_by=user["id"],
            )
        )


def test_duplicate_membership_updates_same_record(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'duplicate.db'}"
    )
    repo.initialize()

    owner = make_user(
        "USR-owner",
        "google-owner",
    )

    repo.save_user(owner)

    organization = make_organization(
        owner["id"]
    )

    repo.save_workspace(organization)

    original = make_membership(
        organization["id"],
        owner["id"],
        role="owner",
        added_by=owner["id"],
    )

    repo.save_organization_membership(
        original
    )

    updated = dict(
        original,
        active=False,
    )

    repo.save_organization_membership(
        updated
    )

    with repo.engine.connect() as connection:
        rows = connection.execute(
            select(
                dbm.organization_memberships
            )
        ).mappings().all()

    assert len(rows) == 1
    assert rows[0]["active"] is False


def test_invalid_membership_role_rejected(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'role.db'}"
    )
    repo.initialize()

    owner = make_user(
        "USR-owner",
        "google-owner",
    )

    repo.save_user(owner)

    organization = make_organization(
        owner["id"]
    )

    repo.save_workspace(organization)

    bad = make_membership(
        organization["id"],
        owner["id"],
        role="superadmin",
        added_by=owner["id"],
    )

    with pytest.raises(
        IntegrityError
    ):
        repo.save_organization_membership(
            bad
        )


def test_inactive_memberships_hidden_by_default(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'inactive.db'}"
    )
    repo.initialize()

    owner = make_user(
        "USR-owner",
        "google-owner",
    )

    member = make_user(
        "USR-member",
        "google-member",
    )

    repo.save_user(owner)
    repo.save_user(member)

    organization = make_organization(
        owner["id"]
    )

    repo.save_workspace(organization)

    membership = make_membership(
        organization["id"],
        member["id"],
        added_by=owner["id"],
    )

    membership["active"] = False

    repo.save_organization_membership(
        membership
    )

    assert (
        repo.list_organization_memberships(
            organization["id"]
        )
        == []
    )

    all_memberships = (
        repo.list_organization_memberships(
            organization["id"],
            active_only=False,
        )
    )

    assert len(all_memberships) == 1


def test_deleting_organization_cascades_memberships(
    tmp_path,
):
    repo = Repository(
        f"sqlite:///{tmp_path / 'cascade.db'}"
    )
    repo.initialize()

    owner = make_user(
        "USR-owner",
        "google-owner",
    )

    repo.save_user(owner)

    organization = make_organization(
        owner["id"]
    )

    repo.save_workspace(organization)

    repo.save_organization_membership(
        make_membership(
            organization["id"],
            owner["id"],
            role="owner",
            added_by=owner["id"],
        )
    )

    with repo.engine.begin() as connection:
        connection.execute(
            dbm.workspaces.delete().where(
                dbm.workspaces.c.id
                == organization["id"]
            )
        )

    with repo.engine.connect() as connection:
        rows = connection.execute(
            select(
                dbm.organization_memberships
            )
        ).all()

    assert rows == []


def test_schema_v4_migrates_additively_to_v10(
    tmp_path,
):
    path = tmp_path / "v4.db"

    old_tables = [
        table
        for table in dbm.metadata.sorted_tables
        if table.name
        != "organization_memberships"
    ]

    repo = Repository(
        f"sqlite:///{path}"
    )

    with repo.engine.begin() as connection:
        for table in old_tables:
            table.create(
                connection,
                checkfirst=True,
            )

        connection.execute(
            insert(dbm.schema_version).values(
                version=4,
                applied_at=(
                    "2026-10-03T00:00:00+00:00"
                ),
            )
        )

    with sqlite3.connect(path) as connection:
        connection.execute(
            "PRAGMA user_version=4"
        )

    repo.initialize()

    names = set(
        inspect(repo.engine).get_table_names()
    )

    assert (
        "organization_memberships"
        in names
    )

    with repo.engine.connect() as connection:
        version = connection.execute(
            select(
                dbm.schema_version.c.version
            )
        ).scalar_one()

    assert version == SCHEMA_VERSION == 13

    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
            == SCHEMA_VERSION
            == 13
        )
