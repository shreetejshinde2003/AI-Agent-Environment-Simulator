"""Phase 4.2.9A persisted simulation workspace ownership tests."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from app.models.schemas import Task, TaskPriority, TaskStatus
from app.storage.database import Repository


def now():
    return datetime.now(timezone.utc)


def make_task(task_id: str, *, workspace_id: str | None = None):
    current = now()
    return Task(
        id=task_id,
        simulation_id=task_id,
        directive="Historical workspace ownership test",
        assigned_agent_id="research",
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.MEDIUM,
        started_at=current,
        created_at=current,
        duration_seconds=0,
        progress_percent=100,
        workspace_id=workspace_id,
    )


def make_user(user_id: str, created_at: str):
    return {
        "id": user_id,
        "google_sub": f"google-{user_id}",
        "email": f"{user_id.lower()}@example.com",
        "display_name": user_id,
        "profile_picture": None,
        "email_verified": True,
        "active": True,
        "created_at": created_at,
        "last_login_at": created_at,
    }


def create_v5_database(path, task: Task):
    """Create only the old V5 simulations/schema_version tables.

    Repository.initialize() creates all other V6 tables before applying the
    additive simulations.workspace_id migration.
    """

    with sqlite3.connect(path) as raw:
        raw.execute(
            "CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at VARCHAR(40) NOT NULL)"
        )
        raw.execute(
            "INSERT INTO schema_version(version, applied_at) VALUES (5, ?)",
            (now().isoformat(),),
        )
        raw.execute(
            """
            CREATE TABLE simulations (
                id VARCHAR(80) PRIMARY KEY,
                owner_id VARCHAR(80),
                dataset_id VARCHAR(80),
                dataset_checksum VARCHAR(64),
                status VARCHAR(30) NOT NULL,
                execution_mode VARCHAR(30) NOT NULL,
                task_type VARCHAR(80),
                created_at VARCHAR(40) NOT NULL,
                started_at VARCHAR(40),
                completed_at VARCHAR(40),
                payload JSON NOT NULL
            )
            """
        )
        raw.execute(
            """
            INSERT INTO simulations(
                id, owner_id, dataset_id, dataset_checksum, status,
                execution_mode, task_type, created_at, started_at,
                completed_at, payload
            ) VALUES (?, NULL, NULL, NULL, ?, ?, NULL, ?, NULL, NULL, ?)
            """,
            (
                task.id,
                task.status.value,
                task.execution_mode.value,
                task.created_at.isoformat(),
                json.dumps(task.model_dump(mode="json")),
            ),
        )
        raw.execute("PRAGMA user_version=5")


def test_v5_migration_adds_nullable_workspace_ownership_without_losing_run(tmp_path):
    path = tmp_path / "v5.db"
    legacy = make_task("T-legacy")
    create_v5_database(path, legacy)

    repository = Repository(f"sqlite:///{path}")
    repository.initialize()

    with sqlite3.connect(path) as raw:
        columns = {row[1] for row in raw.execute("PRAGMA table_info(simulations)")}
        version = raw.execute("SELECT version FROM schema_version").fetchone()[0]
        user_version = raw.execute("PRAGMA user_version").fetchone()[0]

    assert "workspace_id" in columns
    assert version == 8
    assert user_version == 8
    restored = repository.get(legacy.id)
    assert restored is not None
    assert restored.workspace_id is None
    assert restored.directive == legacy.directive


def test_workspace_id_is_persisted_and_workspace_queries_are_scoped(tmp_path):
    repository = Repository(f"sqlite:///{tmp_path / 'owned.db'}")
    repository.initialize()

    created = now().isoformat()
    repository.save_user(make_user("USR-owner", created))
    personal = repository.ensure_personal_workspace("USR-owner")

    owned = make_task("T-owned", workspace_id=personal["id"])
    unowned = make_task("T-unowned")
    repository.save(owned)
    repository.save(unowned)

    reopened = Repository(f"sqlite:///{tmp_path / 'owned.db'}")
    reopened.initialize()

    assert reopened.get(owned.id).workspace_id == personal["id"]
    assert [task.id for task in reopened.list_for_workspace(personal["id"])] == [owned.id]
    assert reopened.get_for_workspace(owned.id, personal["id"]).id == owned.id
    assert reopened.get_for_workspace(unowned.id, personal["id"]) is None


def test_only_oldest_local_user_receives_legacy_shared_history(tmp_path):
    repository = Repository(f"sqlite:///{tmp_path / 'backfill.db'}")
    repository.initialize()

    repository.save(make_task("T-before-auth-1"))
    repository.save(make_task("T-before-auth-2"))

    repository.save_user(make_user("USR-first", "2026-01-01T00:00:00+00:00"))
    repository.save_user(make_user("USR-later", "2026-01-02T00:00:00+00:00"))

    later_personal = repository.ensure_personal_workspace("USR-later")
    first_personal = repository.ensure_personal_workspace("USR-first")

    assert repository.backfill_legacy_simulations_for_user("USR-later") == 0
    assert repository.list_for_workspace(later_personal["id"]) == []

    assert repository.backfill_legacy_simulations_for_user("USR-first") == 2
    assert {task.id for task in repository.list_for_workspace(first_personal["id"])} == {
        "T-before-auth-1",
        "T-before-auth-2",
    }
    assert all(task.workspace_id == first_personal["id"] for task in repository.list())

    # Idempotent on later logins/restarts.
    assert repository.backfill_legacy_simulations_for_user("USR-first") == 0
