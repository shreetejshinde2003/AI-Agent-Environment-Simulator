"""Deterministic activation/readiness tests; no PostgreSQL/provider connection."""

from types import SimpleNamespace

import pytest

from app.security.postgres_rls import (
    DATA_PLANE_RLS_TABLES,
    BOOTSTRAP_RLS_TABLES,
    ACTIVE_RLS_TABLES,
    DEFERRED_RLS_TABLES,
    POLICY_NAME,
    POSTGRES_RLS_POLICIES,
    install_data_plane_rls_policies,
)
from app.security.tenant_db_context import TenantContextError
from app.storage.database import Repository


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value

    def mappings(self):
        return self

    def scalars(self):
        return self

    def one(self):
        return self.value

    def all(self):
        return self.value


class ActivationConnection:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self, *, unsafe_role=False, unassigned=False, enabled=(), policies=None):
        self.unsafe_role = unsafe_role
        self.unassigned = unassigned
        self.enabled = set(enabled)
        self.policies = policies or {}
        self.queries = []
        self.ddl = []

    def execute(self, statement, parameters=None):
        sql = str(statement)
        self.queries.append((sql, parameters))
        if "pg_roles" in sql:
            assert "current_user, session_user" in sql
            assert "pg_has_role(session_user, oid, 'MEMBER')" in sql
            return Result(self.unsafe_role)
        if "FROM pg_class" in sql:
            return Result({"relrowsecurity": parameters["table"] in self.enabled,
                           "relforcerowsecurity": False})
        if "FROM pg_policy" in sql:
            return Result(self.policies.get(parameters["table"], []))
        if "workspace_id IS NULL" in sql:
            return Result(self.unassigned)
        if "schema_version.version" in sql:
            return Result([8])
        pytest.fail(f"Unexpected activation query: {sql}")

    def exec_driver_sql(self, statement):
        self.ddl.append(statement)


def test_activation_keeps_eight_data_tables_and_adds_only_two_bootstrap_tables():
    assert DATA_PLANE_RLS_TABLES == {
        "simulations", "tasks", "agent_executions", "agent_messages",
        "activity_events", "run_events", "simulation_metrics", "simulation_uploads",
    }
    assert BOOTSTRAP_RLS_TABLES == {"workspaces", "organization_memberships"}
    assert DEFERRED_RLS_TABLES == {"organization_human_role_assignments"}
    connection = ActivationConnection()
    install_data_plane_rls_policies(connection)
    expected = tuple(sql for policy in POSTGRES_RLS_POLICIES
                     if policy.table in ACTIVE_RLS_TABLES for sql in policy.ddl())
    assert tuple(connection.ddl) == expected
    assert len(expected) == 40
    for table in ACTIVE_RLS_TABLES:
        assert f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY' in connection.ddl
    assert not any(f'ON "{table}"' in sql for table in DEFERRED_RLS_TABLES
                   for sql in connection.ddl)


def test_unsafe_runtime_credentials_refuse_activation_before_ddl():
    connection = ActivationConnection(unsafe_role=True)
    with pytest.raises(RuntimeError, match="NOSUPERUSER NOBYPASSRLS"):
        install_data_plane_rls_policies(connection)
    assert connection.ddl == []


@pytest.mark.parametrize("table", sorted(DEFERRED_RLS_TABLES))
def test_already_activated_deferred_hr_tables_fail_closed_without_disabling_them(table):
    connection = ActivationConnection(enabled=[table])
    with pytest.raises(RuntimeError, match="readiness checkpoint"):
        install_data_plane_rls_policies(connection)
    assert connection.ddl == []


@pytest.mark.parametrize("table", ["tasks", "workspaces", "organization_memberships"])
def test_unknown_policy_is_not_ored_with_tenant_policy_or_deleted(table):
    connection = ActivationConnection(policies={table: [POLICY_NAME, "allow_all"]})
    with pytest.raises(RuntimeError, match="Unreviewed"):
        install_data_plane_rls_policies(connection)
    assert connection.ddl == []


def test_unassigned_legacy_history_blocks_first_activation_without_claiming_it():
    connection = ActivationConnection(unassigned=True)
    with pytest.raises(RuntimeError, match="no workspace ownership"):
        install_data_plane_rls_policies(connection)
    assert connection.ddl == []


def test_repeat_activation_restores_force_without_unscoped_payload_read():
    connection = ActivationConnection(enabled=DATA_PLANE_RLS_TABLES,
                                      policies={t: [POLICY_NAME] for t in DATA_PLANE_RLS_TABLES})
    install_data_plane_rls_policies(connection)
    assert len(connection.ddl) == 40
    assert not any("FROM simulations" in sql for sql, _ in connection.queries)


def test_sqlite_activation_is_a_noop():
    connection = ActivationConnection()
    connection.dialect = SimpleNamespace(name="sqlite")
    install_data_plane_rls_policies(connection)
    assert connection.ddl == connection.queries == []


@pytest.mark.parametrize("method,args", [
    ("save", (None,)), ("get", ("T-1",)), ("list", ()),
    ("get_for_workspace", ("T-1", "WS-a")), ("list_for_workspace", ("WS-a",)),
])
def test_postgresql_legacy_simulation_methods_reject_before_connecting(method, args):
    repo = Repository("postgresql://unused@localhost/unused")
    try:
        with pytest.raises(TenantContextError, match="trusted workspace and user"):
            getattr(repo, method)(*args)
    finally:
        repo.engine.dispose()


def test_postgresql_login_backfill_never_opens_a_global_ownership_transaction(monkeypatch):
    repo = Repository("postgresql://unused@localhost/unused")
    monkeypatch.setattr(repo, "get_user", lambda *_: pytest.fail("legacy backfill read"))
    try:
        assert repo.backfill_legacy_simulations_for_user("USR-a") == 0
    finally:
        repo.engine.dispose()


def test_postgresql_initialize_installs_only_after_role_and_schema_preflight(monkeypatch):
    from contextlib import contextmanager
    from app.storage import database

    connection = ActivationConnection()

    class Engine:
        dialect = connection.dialect

        @contextmanager
        def begin(self):
            yield connection

    repo = Repository("postgresql://unused@localhost/unused")
    repo._engine = Engine()
    repo._engine_url = repo.url
    created = []
    monkeypatch.setattr(database.dbm.metadata, "create_all", lambda conn: created.append(conn))
    repo.initialize()
    assert created == [connection]
    assert connection.ddl[0] == "SELECT pg_advisory_xact_lock(721842)"
    assert len(connection.ddl) == 41
    connection.unsafe_role = True
    created.clear()
    with pytest.raises(RuntimeError, match="NOSUPERUSER"):
        repo.initialize()
    assert created == []


def test_sqlite_initialize_never_calls_postgres_activation(tmp_path, monkeypatch):
    from app.storage import database

    monkeypatch.setattr(database, "install_data_plane_rls_policies",
                        lambda *_: pytest.fail("PostgreSQL activation on SQLite"))
    repo = Repository(f"sqlite:///{tmp_path / 'local.db'}")
    try:
        repo.initialize()
        repo.initialize()
    finally:
        repo.engine.dispose()
