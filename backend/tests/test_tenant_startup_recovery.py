"""Locked tenant recovery control flow and SQLite compatibility, without providers."""

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import event, select, update

from app.api.routes import tasks
from app.models.schemas import StageExecution, TaskStatus
from app.storage import database, models as dbm
from app.storage.database import Repository, STARTUP_RECOVERY_PRINCIPAL
from test_tenant_repository_primitives import make_task, make_user


@pytest.fixture
def repo(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'recovery.db'}")
    repo.initialize()
    for user_id in ("USR-a", "USR-b"):
        repo.save_user(make_user(user_id))
        repo.ensure_personal_workspace(user_id)
    yield repo
    repo.engine.dispose()


def seed_pending(repo, task_id, workspace_id, *, queued=False):
    task = make_task(task_id, workspace_id)
    task.status = TaskStatus.QUEUED if queued else TaskStatus.IN_PROGRESS
    task.completed_at = None
    task.execution_started_at = None if queued else datetime.now(timezone.utc)
    task.stages = [
        StageExecution(agent_id="research", output_key="research_findings",
                       status="completed", output="Preserved evidence", total_tokens=9),
        StageExecution(agent_id="data", output_key="structured_data",
                       status="waiting" if queued else "active"),
        StageExecution(agent_id="analysis", output_key="insights", status="waiting"),
    ]
    repo.save(task)
    return task


def test_sqlite_recovery_preserves_old_unowned_history_and_is_idempotent(repo, monkeypatch):
    ws_a = repo.get_personal_workspace("USR-a")["id"]
    seed_pending(repo, "T-a", ws_a)
    seed_pending(repo, "T-legacy", None, queued=True)
    done = make_task("T-done", ws_a)
    done.output = "Completed result"
    repo.save(done)
    monkeypatch.setattr(tasks, "repository", repo)
    monkeypatch.setattr(repo, "list", lambda: pytest.fail("global recovery list"))
    monkeypatch.setattr(repo, "save", lambda *_: pytest.fail("legacy recovery save"))
    assert tasks.recover_interrupted() == 2
    assert tasks.recover_interrupted() == 0
    failed = repo.get("T-a")
    assert failed.status == TaskStatus.FAILED
    assert failed.output is None
    assert [s.status for s in failed.stages] == ["completed", "failed", "waiting"]
    assert failed.stages[0].output == "Preserved evidence"
    assert failed.stages[0].total_tokens == 9
    assert failed.stages[2].started_at is None
    assert failed.messages == []
    assert len(failed.events) == 1
    assert failed.events[0].type == "simulation_failed"
    assert repo.get("T-done").output == "Completed result"
    legacy = repo.get("T-legacy")
    assert legacy.workspace_id is None
    assert legacy.elapsed_seconds is None
    assert legacy.stages[1].status == "waiting"
    with repo.engine.connect() as connection:
        assert connection.execute(select(dbm.tasks.c.status).where(
            dbm.tasks.c.id == "T-a")).scalar_one() == "failed"
        assert connection.execute(select(dbm.run_events.c.type).where(
            dbm.run_events.c.simulation_id == "T-a")).scalars().all() == ["simulation_failed"]


def test_pg_recovery_control_flow_uses_only_catalog_globally_and_locks_each_tenant(repo, monkeypatch):
    """SQLite-backed recording engine tests PG branching, NOT PG enforcement."""
    ws_a = repo.get_personal_workspace("USR-a")["id"]
    ws_b = repo.get_personal_workspace("USR-b")["id"]
    seed_pending(repo, "T-a", ws_a)
    seed_pending(repo, "T-b", ws_b, queued=True)
    with repo.engine.begin() as connection:
        connection.execute(update(dbm.workspaces).where(
            dbm.workspaces.c.id == ws_b).values(active=False))
    sqlite_engine = repo.engine
    contexts = []
    active_context = []
    reads = []

    class RecordingEngine:
        dialect = SimpleNamespace(name="postgresql")

        def connect(self):
            return sqlite_engine.connect()

    @contextmanager
    def recording_tenant_transaction(engine, *, workspace_id, user_id):
        assert engine is repo.engine
        contexts.append((workspace_id, user_id))
        active_context.append(workspace_id)
        try:
            with sqlite_engine.begin() as connection:
                yield connection
        finally:
            active_context.clear()

    def record_query(connection, statement, *args):
        if getattr(statement, "is_select", False):
            sql = str(statement)
            if "FROM simulations" in sql:
                assert len(active_context) == 1
                if "simulations.payload" in sql:
                    assert statement._for_update_arg is not None
                    assert "simulations.workspace_id =" in sql
                    reads.append(active_context[0])
            elif not active_context:
                assert "FROM workspaces" in sql

    event.listen(sqlite_engine, "before_execute", record_query)
    monkeypatch.setattr(database, "tenant_transaction", recording_tenant_transaction)
    monkeypatch.setattr(repo, "_engine", RecordingEngine())
    try:
        assert repo.recover_interrupted_tasks(tasks._mark_interrupted_failed) == 2
        assert contexts == [(ws, STARTUP_RECOVERY_PRINCIPAL) for ws in sorted([ws_a, ws_b])]
        assert reads == sorted([ws_a, ws_b])
        assert active_context == []
        assert repo.recover_interrupted_tasks(tasks._mark_interrupted_failed) == 0
    finally:
        repo._engine = sqlite_engine
        event.remove(sqlite_engine, "before_execute", record_query)
    assert repo.get("T-b").status == TaskStatus.FAILED


def test_recovery_transaction_rolls_back_if_persistence_fails(repo, monkeypatch):
    ws = repo.get_personal_workspace("USR-a")["id"]
    seed_pending(repo, "T-a", ws)
    original = repo._save_task

    def fail_after_write(connection, task):
        original(connection, task)
        raise RuntimeError("controlled storage failure")

    monkeypatch.setattr(repo, "_save_task", fail_after_write)
    with pytest.raises(RuntimeError, match="controlled storage failure"):
        repo.recover_interrupted_tasks(tasks._mark_interrupted_failed)
    assert repo.get("T-a").status == TaskStatus.IN_PROGRESS
    assert repo.get("T-a").events == []
