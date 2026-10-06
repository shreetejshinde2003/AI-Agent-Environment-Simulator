"""Phase 4.5.5C.1 upload ownership schema and migration tests."""

from datetime import datetime, timezone

from sqlalchemy import inspect, insert, select

from app.storage import models as dbm
from app.storage.database import Repository, SCHEMA_VERSION


def _seed_user_and_workspaces(connection):
    now = datetime.now(timezone.utc).isoformat()

    connection.execute(insert(dbm.users).values(
        id="USR-a",
        google_sub="google-a",
        email="a@example.com",
        display_name="A",
        profile_picture=None,
        email_verified=True,
        active=True,
        created_at=now,
        last_login_at=now,
    ))

    for workspace_id in ("WS-a", "WS-b"):
        connection.execute(insert(dbm.workspaces).values(
            id=workspace_id,
            kind="organization",
            name=workspace_id,
            personal_owner_user_id=None,
            created_by_user_id="USR-a",
            join_code_digest=None,
            active=True,
            created_at=now,
            updated_at=now,
        ))

    return now


def _insert_simulation(connection, simulation_id, workspace_id, now):
    connection.execute(insert(dbm.simulations).values(
        id=simulation_id,
        owner_id=None,
        workspace_id=workspace_id,
        dataset_id=None,
        dataset_checksum=None,
        status="completed",
        execution_mode="single",
        task_type=None,
        created_at=now,
        started_at=None,
        completed_at=now,
        payload={},
    ))


def _insert_unowned_upload(connection, upload_id, now):
    connection.execute(insert(dbm.uploads).values(
        id=upload_id,
        workspace_id=None,
        created_by_user_id=None,
        filename="legacy.txt",
        format="txt",
        size_bytes=6,
        created_at=now,
        payload={},
    ))


def test_v9_upload_schema_has_explicit_nullable_ownership(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'fresh.db'}")
    repo.initialize()

    columns = {
        column["name"]: column
        for column in inspect(repo.engine).get_columns("uploads")
    }

    assert SCHEMA_VERSION == 12
    assert columns["workspace_id"]["nullable"] is True
    assert columns["created_by_user_id"]["nullable"] is True

    assert (
        next(iter(dbm.uploads.c.workspace_id.foreign_keys)).target_fullname
        == "workspaces.id"
    )

    assert (
        next(iter(dbm.uploads.c.created_by_user_id.foreign_keys)).target_fullname
        == "users.id"
    )


def test_backfill_derives_one_unambiguous_workspace_without_creator(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'backfill.db'}")
    repo.initialize()

    with repo.engine.begin() as connection:
        now = _seed_user_and_workspaces(connection)

        _insert_simulation(connection, "SIM-a", "WS-a", now)
        _insert_unowned_upload(connection, "U-a", now)

        connection.execute(insert(dbm.simulation_uploads).values(
            simulation_id="SIM-a",
            upload_id="U-a",
        ))

        repo._ensure_upload_ownership_columns(connection)

        row = connection.execute(
            select(
                dbm.uploads.c.workspace_id,
                dbm.uploads.c.created_by_user_id,
            ).where(dbm.uploads.c.id == "U-a")
        ).one()

    assert row.workspace_id == "WS-a"
    assert row.created_by_user_id is None


def test_backfill_does_not_guess_orphan_workspace(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'orphan.db'}")
    repo.initialize()

    with repo.engine.begin() as connection:
        now = _seed_user_and_workspaces(connection)

        _insert_unowned_upload(connection, "U-orphan", now)

        repo._ensure_upload_ownership_columns(connection)

        workspace_id = connection.execute(
            select(dbm.uploads.c.workspace_id)
            .where(dbm.uploads.c.id == "U-orphan")
        ).scalar_one()

    assert workspace_id is None


def test_backfill_does_not_guess_conflicting_workspaces(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'conflict.db'}")
    repo.initialize()

    with repo.engine.begin() as connection:
        now = _seed_user_and_workspaces(connection)

        _insert_simulation(connection, "SIM-a", "WS-a", now)
        _insert_simulation(connection, "SIM-b", "WS-b", now)
        _insert_unowned_upload(connection, "U-conflict", now)

        connection.execute(insert(dbm.simulation_uploads), [
            {
                "simulation_id": "SIM-a",
                "upload_id": "U-conflict",
            },
            {
                "simulation_id": "SIM-b",
                "upload_id": "U-conflict",
            },
        ])

        repo._ensure_upload_ownership_columns(connection)

        workspace_id = connection.execute(
            select(dbm.uploads.c.workspace_id)
            .where(dbm.uploads.c.id == "U-conflict")
        ).scalar_one()

    assert workspace_id is None


def test_upload_ownership_helper_is_idempotent(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'idempotent.db'}")
    repo.initialize()

    with repo.engine.begin() as connection:
        repo._ensure_upload_ownership_columns(connection)
        repo._ensure_upload_ownership_columns(connection)
