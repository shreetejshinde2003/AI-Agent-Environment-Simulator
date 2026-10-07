"""Database and benchmark tests; no provider calls or external PostgreSQL server."""

import json
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.datasets.registry import BENCHMARK_DIR, context_for_dataset, register_all, validate_dataset
from app.models.schemas import (ActivityEvent, Message, MessageKind, RunEvent,
                                StageExecution, Task, TaskPriority, TaskStatus,
                                UploadedContext)
from app.storage.database import Repository, SCHEMA_VERSION, normalize_url
from app.storage import models as dbm

HAS_LOCAL_BENCHMARKS = all((BENCHMARK_DIR / f"{family}_{size}.json").is_file()
                           for family in ("employee", "hr") for size in ("small", "medium", "large"))
requires_local_benchmarks = pytest.mark.skipif(
    not HAS_LOCAL_BENCHMARKS, reason="Private benchmark JSON files are not provisioned")


@pytest.fixture
def repo(tmp_path):
    repository = Repository(f"sqlite:///{tmp_path / 'test.db'}")
    repository.initialize()
    return repository


def example_task(now, status=TaskStatus.COMPLETED):
    upload = UploadedContext(id="U-1", filename="brief.txt", format="txt", size_bytes=5,
                             created_at=now, preview="brief", prepared_context="brief")
    return Task(id="T-1", directive="Explain the finding", assigned_agent_id="orchestrator",
                status=status, priority=TaskPriority.MEDIUM, started_at=now,
                created_at=now, duration_seconds=1, progress_percent=100,
                output="real report" if status == TaskStatus.COMPLETED else None,
                error="controlled error" if status == TaskStatus.FAILED else None,
                stages=[StageExecution(agent_id="research", output_key="research_findings",
                                       status="completed", output="real finding", total_tokens=7,
                                       model="test-model"),
                        StageExecution(agent_id="data", output_key="structured_data",
                                       status="failed" if status == TaskStatus.FAILED else "completed",
                                       error="controlled error" if status == TaskStatus.FAILED else None)],
                messages=[Message(id="M-1", from_agent_id="research", to_agent_id="data",
                                  kind=MessageKind.RESPONSE, content="real finding", timestamp=now)],
                activities=[ActivityEvent(id="A-1", agent_id="research", text="completed", timestamp=now)],
                events=[RunEvent(id="E-1", type="agent_completed", text="research completed",
                                 agent_id="research", timestamp=now)], uploads=[upload])


def test_sqlite_fallback_and_relational_state(repo):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    run = example_task(now)
    repo.save(run)
    reopened = Repository(repo.url)
    reopened.initialize()
    saved = reopened.get(run.id)
    assert saved.output == run.output
    assert len(saved.messages) == len(saved.events) == len(saved.activities) == 1
    assert reopened.get_upload("U-1").prepared_context == "brief"
    with reopened.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        for table, count in ((dbm.simulations, 1), (dbm.tasks, 1), (dbm.agent_executions, 2),
                             (dbm.agent_messages, 1), (dbm.run_events, 1),
                             (dbm.activity_events, 1), (dbm.uploads, 1),
                             (dbm.simulation_uploads, 1)):
            assert len(connection.execute(select(table)).all()) == count
        metrics = connection.execute(select(dbm.simulation_metrics)).mappings().one()
        assert metrics["total_tokens"] == 7 and metrics["measured_stages"] == 1
    run.status = TaskStatus.FAILED
    run.error = "controlled error"
    run.output = None
    run.stages[1].status = "failed"
    run.stages[1].error = "controlled error"
    repo.save(run)
    assert reopened.get(run.id).status == TaskStatus.FAILED
    with reopened.engine.connect() as connection:
        assert connection.execute(select(dbm.tasks.c.error)).scalar_one() == "controlled error"
        assert len(connection.execute(select(dbm.agent_messages)).all()) == 1


def test_v1_snapshot_migration_preserves_data(tmp_path):
    from datetime import datetime, timezone
    path = tmp_path / "legacy.db"
    task = example_task(datetime.now(timezone.utc))
    with sqlite3.connect(path) as connection:
        connection.executescript("""CREATE TABLE simulations (id TEXT PRIMARY KEY, owner_id TEXT,
            status TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE uploads (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE agent_roster (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            PRAGMA user_version=1;""")
        connection.execute("INSERT INTO simulations VALUES (?,?,?,?,?)",
                           (task.id, None, task.status.value, task.created_at.isoformat(), task.model_dump_json()))
        connection.execute("INSERT INTO uploads VALUES (?,?)", ("U-1", task.uploads[0].model_dump_json()))
        connection.execute("INSERT INTO agent_roster VALUES (?,?)", ("custom", json.dumps({"id": "custom"})))
    repo = Repository(f"sqlite:///{path}")
    repo.initialize()
    assert repo.get(task.id).output == "real report"
    assert repo.get_upload("U-1").filename == "brief.txt"
    assert repo.agents() == [{"id": "custom"}]
    assert {"simulations_v1_archive", "uploads_v1_archive", "agent_roster_v1_archive"} <= set(
        inspect(repo.engine).get_table_names())
    assert len(list(tmp_path.glob("legacy.db.v1.*.db"))) == 1
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    repo.initialize()  # idempotent


def test_postgresql_configuration_without_server():
    assert normalize_url(None) == "sqlite:///./simulator.db"
    assert normalize_url("postgres://user:password@host/db") == "postgresql+psycopg://user:password@host/db"
    repo = Repository("postgresql://user:password@host/db")
    assert repo.engine.dialect.name == "postgresql"
    assert "JSONB" in str(dbm.simulations.c.payload.type.compile(dialect=postgresql.dialect()))
    assert all("CREATE TABLE" in str(CreateTable(table).compile(dialect=postgresql.dialect()))
               for table in dbm.metadata.sorted_tables)
    repo.engine.dispose()  # no connection attempted


@pytest.mark.parametrize("previous_version", [2, 9, 12])
def test_completed_legacy_migration_can_upgrade_with_retained_archives(tmp_path, previous_version):
    """An archive is evidence of a completed migration after schema version 1."""
    test_v1_snapshot_migration_preserves_data(tmp_path)
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        archives = connection.execute("SELECT payload FROM simulations_v1_archive").fetchall()
        connection.execute("UPDATE schema_version SET version=?", (previous_version,))
        connection.execute(f"PRAGMA user_version={previous_version}")
    repo = Repository(f"sqlite:///{path}")
    try:
        repo.initialize()
        repo.initialize()
        assert repo.get("T-1").output == "real report"
        assert repo.get_upload("U-1").prepared_context == "brief"
        with sqlite3.connect(path) as connection:
            assert connection.execute("SELECT payload FROM simulations_v1_archive").fetchall() == archives
            assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
            assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == SCHEMA_VERSION
        assert len(list(tmp_path.glob("legacy.db.v1.*.db"))) == 1
    finally:
        repo.engine.dispose()


def test_interrupted_legacy_migration_with_archives_still_fails_closed(tmp_path):
    path = tmp_path / "interrupted.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("CREATE TABLE simulations_v1_archive (id TEXT); PRAGMA user_version=1;")
    repo = Repository(f"sqlite:///{path}")
    try:
        with pytest.raises(RuntimeError, match="Interrupted V1 migration"):
            repo.initialize()
        with sqlite3.connect(path) as connection:
            assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    finally:
        repo.engine.dispose()


@requires_local_benchmarks
def test_registry_six_datasets_and_safe_context(repo):
    records = register_all(repo)
    assert {(item["dataset_id"], item["record_count"]) for item in records} == {
        ("employee_small", 294), ("employee_medium", 735), ("employee_large", 1470),
        ("hr_small", 62), ("hr_medium", 155), ("hr_large", 311)}
    assert len(repo.list_datasets()) == 6
    assert repo.get_dataset("hr_large")["quality"]["manager_id_nan_as_null"] == 8
    for item in records:
        context = context_for_dataset(item)
        assert 0 < len(context) <= 3500
        for excluded in ("EmployeeName", "EmployeeID", "ManagerID", "Gender", "Age", "Salary"):
            assert excluded not in context
    with repo.engine.connect() as connection:
        assert "benchmark_records" not in inspect(repo.engine).get_table_names()
        assert len(connection.execute(select(dbm.dataset_registry)).all()) == 6


@pytest.mark.parametrize("bad", [
    [{"EmployeeID": 1}],
    [{"EmployeeID": 1, "Age": 30, "Gender": "F", "Department": "A", "JobRole": "B",
      "JobLevel": 1, "Salary": 10, "YearsAtCompany": 1, "PerformanceRating": 3}] * 2,
])
def test_malformed_employee_dataset_rejected(tmp_path, bad):
    path = tmp_path / "employee_small.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        validate_dataset(path, "employee_small")


def test_nonstandard_nan_only_allowed_in_hr_manager(tmp_path):
    path = tmp_path / "employee_small.json"
    path.write_text('[{"EmployeeID":1,"Age":NaN,"Gender":"F","Department":"A",'
                    '"JobRole":"B","JobLevel":1,"Salary":10,"YearsAtCompany":1,'
                    '"PerformanceRating":3}]')
    with pytest.raises(ValueError):
        validate_dataset(path, "employee_small")


def test_registry_operates_without_private_files(repo, tmp_path):
    examples = {
        "employee": {"EmployeeID": 1, "Age": 30, "Gender": "X", "Department": "Engineering",
                     "JobRole": "Analyst", "JobLevel": 2, "Salary": 1000,
                     "YearsAtCompany": 2, "PerformanceRating": 3},
        "hr": {"EmployeeID": 10001, "EmployeeName": "Test Person",
               "Department": "Engineering", "JobRole": "Analyst",
               "ManagerID": None, "Salary": 1000, "Status": "Active"},
    }
    for family, row in examples.items():
        for size in ("small", "medium", "large"):
            (tmp_path / f"{family}_{size}.json").write_text(json.dumps([row]))
    registered = register_all(repo, tmp_path)
    assert len(registered) == 6
    assert len(repo.list_datasets()) == 6
    context = context_for_dataset(repo.get_dataset("hr_small"), tmp_path)
    assert "Engineering=1" in context
    assert "Test Person" not in context
    before = repo.get_dataset("hr_medium")["checksum"]
    changed = dict(examples["hr"], Department="Different")
    (tmp_path / "hr_medium.json").write_text(json.dumps([changed]))
    with pytest.raises(ValueError, match="nested prefixes"):
        register_all(repo, tmp_path)
    assert repo.get_dataset("hr_medium")["checksum"] == before


@requires_local_benchmarks
def test_checksum_change_rejected(repo, tmp_path):
    record = register_all(repo)[0]
    source = BENCHMARK_DIR / record["source_filename"]
    copy = tmp_path / source.name
    copy.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="changed since registration"):
        context_for_dataset(record, tmp_path)


@requires_local_benchmarks
def test_registration_rejects_one_malformed_file_without_partial_registry(repo, tmp_path):
    for source in BENCHMARK_DIR.glob("*.json"):
        destination = tmp_path / source.name
        if source.name == "hr_medium.json":
            destination.write_text("not JSON")
        else:
            destination.symlink_to(source)
    with pytest.raises(ValueError):
        register_all(repo, tmp_path)
    assert repo.list_datasets() == []


@requires_local_benchmarks
def test_inactive_dataset_cannot_enter_context(repo):
    record = register_all(repo)[0]
    record["active"] = False
    repo.save_dataset(record)
    with pytest.raises(ValueError, match="inactive"):
        context_for_dataset(repo.get_dataset(record["dataset_id"]))
    register_all(repo)
    assert repo.get_dataset(record["dataset_id"])["active"] is False
