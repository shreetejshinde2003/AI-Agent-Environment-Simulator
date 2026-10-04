"""Opt-in real PostgreSQL enforcement tests in a disposable isolated local schema.

Requires TENANT_TEST_DATABASE_URL pointing to a *local test* PostgreSQL database
with a NOSUPERUSER/NOBYPASSRLS schema-creating login. Never uses DATABASE_URL or
production data. No LLMs, providers, or HTTP simulations are invoked.
"""

import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, delete, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.api.routes.tasks import _mark_interrupted_failed
from app.models.schemas import TaskStatus
from app.security.postgres_rls import ACTIVE_RLS_TABLES, DATA_PLANE_RLS_TABLES, DEFERRED_RLS_TABLES, require_rls_runtime_role
from app.security.tenant_db_context import CURRENT_USER_SQL, CURRENT_WORKSPACE_SQL, tenant_transaction
from app.storage import models as dbm
from app.storage.database import Repository, normalize_url
from test_phase2_storage import example_task
from test_tenant_repository_primitives import make_user


@pytest.fixture
def pg_repo():
    raw_url = os.environ.get("TENANT_TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("TENANT_TEST_DATABASE_URL not set; live PostgreSQL enforcement unverified")
    url = make_url(normalize_url(raw_url))
    if (url.get_backend_name() != "postgresql"
            or url.host not in {"localhost", "127.0.0.1", "::1"}
            or {"host", "hostaddr", "service"} & set(url.query)):
        pytest.fail("TENANT_TEST_DATABASE_URL must be an isolated local PostgreSQL test database")
    schema = f"tenant_test_{uuid.uuid4().hex}"
    admin = create_engine(url)
    # Reject superuser credentials even for setup; no BYPASSRLS fixture role.
    with admin.begin() as connection:
        require_rls_runtime_role(connection)
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine = create_engine(url, pool_size=1, max_overflow=0,
                           connect_args={"options": f"-csearch_path={schema},pg_catalog"})
    repo = Repository(url.render_as_string(hide_password=False))
    repo._engine = engine
    repo._engine_url = repo.url
    try:
        repo.initialize()
        for uid in ("USR-a", "USR-b"):
            repo.save_user(make_user(uid))
            repo.ensure_personal_workspace(uid)
        yield repo
    finally:
        engine.dispose()
        with admin.begin() as connection:
            # Exact random test-owned schema only; never application schema/data.
            connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


def seed(repo, task_id, uid):
    task = example_task(datetime.now(timezone.utc))
    task.id = task_id
    task.simulation_id = task_id
    task.workspace_id = repo.get_personal_workspace(uid)["id"]
    for record in (*task.messages, *task.activities, *task.events):
        record.id = f"{record.id}-{task_id}"
    repo.save_for_tenant(task, workspace_id=task.workspace_id, user_id=uid)
    return task


def test_live_activation_force_and_deferred_tables(pg_repo):
    pg_repo.initialize()  # Repeat activation remains safe.
    with pg_repo.engine.connect() as connection:
        for table in sorted(ACTIVE_RLS_TABLES | DEFERRED_RLS_TABLES | {"uploads"}):
            row = connection.execute(text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = to_regclass(:table)"
            ), {"table": table}).one()
            assert tuple(row) == ((True, True) if table in ACTIVE_RLS_TABLES else (False, False))


def test_live_data_plane_filters_unscoped_queries_and_other_tenants(pg_repo):
    a = seed(pg_repo, "T-a", "USR-a")
    b = seed(pg_repo, "T-b", "USR-b")
    tables = [dbm.metadata.tables[name] for name in sorted(DATA_PLANE_RLS_TABLES)]
    with pg_repo.engine.connect() as connection:
        for table in tables:
            assert connection.execute(select(table)).all() == []
    with tenant_transaction(pg_repo.engine, workspace_id=a.workspace_id, user_id="USR-a") as connection:
        for table in tables:
            rows = connection.execute(select(table)).mappings().all()
            assert rows
            assert all(row["id" if table is dbm.simulations else "simulation_id"] == a.id for row in rows)
        assert connection.execute(update(dbm.simulations).where(
            dbm.simulations.c.id == b.id).values(status="failed")).rowcount == 0
        assert connection.execute(delete(dbm.agent_messages).where(
            dbm.agent_messages.c.simulation_id == b.id)).rowcount == 0
    assert pg_repo.get_for_tenant(b.id, workspace_id=a.workspace_id, user_id="USR-a") is None
    assert pg_repo.get_for_tenant(b.id, workspace_id=b.workspace_id, user_id="USR-b").status.value == "completed"


def test_live_cross_tenant_inserts_and_workspace_moves_are_rejected(pg_repo):
    a = seed(pg_repo, "T-a", "USR-a")
    b = seed(pg_repo, "T-b", "USR-b")
    with pytest.raises(DBAPIError):
        with tenant_transaction(pg_repo.engine, workspace_id=a.workspace_id, user_id="USR-a") as connection:
            connection.execute(insert(dbm.run_events).values(
                id="wrong", simulation_id=b.id, type="simulation_failed",
                timestamp=datetime.now(timezone.utc).isoformat(), text="Must never persist"))
    with pytest.raises(DBAPIError):
        with tenant_transaction(pg_repo.engine, workspace_id=a.workspace_id, user_id="USR-a") as connection:
            connection.execute(update(dbm.simulations).where(
                dbm.simulations.c.id == a.id).values(workspace_id=b.workspace_id))
    with pytest.raises(DBAPIError):
        with pg_repo.engine.begin() as connection:
            connection.execute(insert(dbm.run_events).values(
                id="unscoped", simulation_id=a.id, type="simulation_failed",
                timestamp=datetime.now(timezone.utc).isoformat(), text="No context"))


@pytest.mark.parametrize("rollback", [False, True])
def test_live_same_pooled_connection_clears_context_after_commit_and_rollback(pg_repo, rollback):
    a = seed(pg_repo, "T-a", "USR-a")
    b = seed(pg_repo, "T-b", "USR-b")
    class Abort(Exception):
        pass

    @contextmanager
    def expected_result():
        if rollback:
            with pytest.raises(Abort):
                yield
        else:
            yield

    with expected_result():
        with tenant_transaction(pg_repo.engine, workspace_id=a.workspace_id, user_id="USR-a") as connection:
            backend_pid = connection.execute(text("SELECT pg_backend_pid()")).scalar_one()
            assert connection.execute(select(dbm.simulations.c.id)).scalars().all() == [a.id]
            if rollback:
                raise Abort()
    with pg_repo.engine.connect() as connection:
        assert connection.execute(text("SELECT pg_backend_pid()")).scalar_one() == backend_pid
        assert connection.execute(text(f"SELECT {CURRENT_WORKSPACE_SQL}, {CURRENT_USER_SQL}")).one() == (None, None)
        assert connection.execute(select(dbm.simulations)).all() == []
    with tenant_transaction(pg_repo.engine, workspace_id=b.workspace_id, user_id="USR-b") as connection:
        assert connection.execute(select(dbm.simulations.c.id)).scalars().all() == [b.id]


def test_live_recovery_under_force_rls_is_tenant_scoped_and_idempotent(pg_repo):
    a = seed(pg_repo, "T-a", "USR-a")
    b = seed(pg_repo, "T-b", "USR-b")
    for task in (a, b):
        task.status = TaskStatus.IN_PROGRESS
        task.execution_started_at = datetime.now(timezone.utc)
        task.stages[1].status = "active"
        pg_repo.save_for_tenant(task, workspace_id=task.workspace_id, user_id="USR-a" if task.id == a.id else "USR-b")
    assert pg_repo.recover_interrupted_tasks(_mark_interrupted_failed) == 2
    assert pg_repo.recover_interrupted_tasks(_mark_interrupted_failed) == 0
    for task, uid in ((a, "USR-a"), (b, "USR-b")):
        persisted = pg_repo.get_for_tenant(task.id, workspace_id=task.workspace_id, user_id=uid)
        assert persisted.status.value == "failed"
        assert persisted.output is None
        assert [s.status for s in persisted.stages] == ["completed", "failed"]
        assert len(persisted.messages) == 1  # Original evidence, not fabricated.
        assert persisted.events[-1].type == "simulation_failed"
