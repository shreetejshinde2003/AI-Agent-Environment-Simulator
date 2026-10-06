"""Phase 4.2.1 workspace/tenancy storage tests."""

import sqlite3
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, insert, select
from sqlalchemy.exc import IntegrityError

from app.storage import models as dbm
from app.storage.database import Repository, SCHEMA_VERSION


def now_text():
    return datetime.now(timezone.utc).isoformat()


def make_user(user_id="USR-a", google_sub="google-a"):
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


def make_personal_workspace(user_id="USR-a"):
    now = now_text()

    return {
        "id": "WS-personal-a",
        "kind": "personal",
        "name": "Personal Workspace",
        "personal_owner_user_id": user_id,
        "created_by_user_id": user_id,
        "join_code_digest": None,
        "active": True,
        "created_at": now,
        "updated_at": now,
    }


def test_fresh_v10_database_contains_workspaces(tmp_path):
    repo = Repository(
        f"sqlite:///{tmp_path / 'workspace.db'}"
    )

    repo.initialize()

    names = set(
        inspect(repo.engine).get_table_names()
    )

    assert "workspaces" in names

    with sqlite3.connect(repo.path) as connection:
        assert (
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
            == SCHEMA_VERSION
            == 11
        )


def test_personal_workspace_round_trip(tmp_path):
    repo = Repository(
        f"sqlite:///{tmp_path / 'personal.db'}"
    )
    repo.initialize()

    user = make_user()
    repo.save_user(user)

    workspace = make_personal_workspace()
    repo.save_workspace(workspace)

    restored = repo.get_workspace(
        workspace["id"]
    )

    by_owner = repo.get_personal_workspace(
        user["id"]
    )

    assert restored == by_owner
    assert restored["kind"] == "personal"
    assert (
        restored["personal_owner_user_id"]
        == user["id"]
    )
    assert restored["join_code_digest"] is None
    assert restored["active"] is True


def test_one_personal_workspace_per_user(tmp_path):
    repo = Repository(
        f"sqlite:///{tmp_path / 'unique-personal.db'}"
    )
    repo.initialize()

    user = make_user()
    repo.save_user(user)

    first = make_personal_workspace()
    second = dict(
        first,
        id="WS-personal-b",
    )

    repo.save_workspace(first)

    with pytest.raises(IntegrityError):
        repo.save_workspace(second)


def test_organization_is_not_a_personal_workspace(tmp_path):
    repo = Repository(
        f"sqlite:///{tmp_path / 'organization.db'}"
    )
    repo.initialize()

    user = make_user()
    repo.save_user(user)

    now = now_text()

    organization = {
        "id": "WS-org-a",
        "kind": "organization",
        "name": "Example Organization",
        "personal_owner_user_id": None,
        "created_by_user_id": user["id"],
        "join_code_digest": None,
        "active": True,
        "created_at": now,
        "updated_at": now,
    }

    repo.save_workspace(organization)

    restored = repo.get_workspace(
        organization["id"]
    )

    assert restored["kind"] == "organization"
    assert restored["personal_owner_user_id"] is None
    assert (
        repo.get_personal_workspace(user["id"])
        is None
    )


def test_workspace_kind_constraint_is_enforced(tmp_path):
    repo = Repository(
        f"sqlite:///{tmp_path / 'kind.db'}"
    )
    repo.initialize()

    user = make_user()
    repo.save_user(user)

    bad = make_personal_workspace()
    bad["id"] = "WS-invalid"
    bad["kind"] = "something_else"

    with pytest.raises(IntegrityError):
        repo.save_workspace(bad)


def test_personal_workspace_requires_owner(tmp_path):
    repo = Repository(
        f"sqlite:///{tmp_path / 'owner.db'}"
    )
    repo.initialize()

    user = make_user()
    repo.save_user(user)

    bad = make_personal_workspace()
    bad["id"] = "WS-invalid-owner"
    bad["personal_owner_user_id"] = None

    with pytest.raises(IntegrityError):
        repo.save_workspace(bad)


def test_schema_v3_migrates_additively_to_v10(tmp_path):
    path = tmp_path / "v3.db"

    old_tables = [
        table
        for table in dbm.metadata.sorted_tables
        if table.name != "workspaces"
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
                version=3,
                applied_at="2026-10-02T00:00:00+00:00",
            )
        )

    with sqlite3.connect(path) as connection:
        connection.execute(
            "PRAGMA user_version=3"
        )

    repo.initialize()

    names = set(
        inspect(repo.engine).get_table_names()
    )

    assert "workspaces" in names

    with repo.engine.connect() as connection:
        version = connection.execute(
            select(dbm.schema_version.c.version)
        ).scalar_one()

    assert version == SCHEMA_VERSION == 11

    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
            == SCHEMA_VERSION
            == 11
        )


def test_workspace_schema_contains_no_plain_join_code():
    columns = {
        column.name
        for column in dbm.workspaces.columns
    }

    assert "join_code" not in columns
    assert "join_code_digest" in columns
