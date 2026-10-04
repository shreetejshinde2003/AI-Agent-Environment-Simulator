"""Phase 4.5.2 trusted PostgreSQL tenant-session context tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from app.security.tenant_db_context import (
    CURRENT_USER_SQL,
    CURRENT_WORKSPACE_SQL,
    TenantContextError,
    TenantSessionContext,
    apply_tenant_session_context,
    tenant_transaction,
)


class RecordingPostgresConnection:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self):
        self.calls = []

    def execute(self, statement, parameters):
        self.calls.append((str(statement), parameters))


class RecordingEngine:
    def __init__(self, connection):
        self.connection = connection
        self.entered = False
        self.exited = False

    class _Begin:
        def __init__(self, owner):
            self.owner = owner

        def __enter__(self):
            self.owner.entered = True
            return self.owner.connection

        def __exit__(self, exc_type, exc, tb):
            self.owner.exited = True
            return False

    def begin(self):
        return self._Begin(self)


def test_validated_context_requires_both_canonical_identifiers():
    context = TenantSessionContext.validated(
        workspace_id="WS-tenant",
        user_id="USR-user",
    )
    assert context.workspace_id == "WS-tenant"
    assert context.user_id == "USR-user"

    invalid = ("", " ", " WS-tenant", "WS-tenant ", "abc\x00def")
    for value in invalid:
        with pytest.raises(TenantContextError):
            TenantSessionContext.validated(workspace_id=value, user_id="USR-user")
        with pytest.raises(TenantContextError):
            TenantSessionContext.validated(workspace_id="WS-tenant", user_id=value)


def test_postgresql_context_is_parameterized_and_transaction_local():
    connection = RecordingPostgresConnection()

    result = apply_tenant_session_context(
        connection,
        workspace_id="WS-tenant",
        user_id="USR-user",
    )

    assert result.workspace_id == "WS-tenant"
    assert len(connection.calls) == 1
    sql, parameters = connection.calls[0]
    assert "set_config" in sql
    assert ":workspace_id" in sql
    assert ":user_id" in sql
    assert "true" in sql.lower()
    assert "WS-tenant" not in sql
    assert "USR-user" not in sql
    assert parameters == {
        "workspace_setting": "app.current_workspace_id",
        "workspace_id": "WS-tenant",
        "user_setting": "app.current_user_id",
        "user_id": "USR-user",
        "invitation_setting": "app.invitation_digest",
        "invitation_digest": "",
        "invitation_workspace_setting": "app.invitation_workspace_id",
        "invitation_workspace_id": "",
        "recovery_setting": "app.recovery_owner_user_id",
        "recovery_owner_user_id": "",
    }


def test_tenant_transaction_validates_before_opening_database_transaction():
    engine = RecordingEngine(RecordingPostgresConnection())

    with pytest.raises(TenantContextError):
        with tenant_transaction(engine, workspace_id="", user_id="USR-user"):
            pass

    assert engine.entered is False
    assert engine.exited is False


def test_tenant_transaction_sets_context_before_yielding_connection():
    connection = RecordingPostgresConnection()
    engine = RecordingEngine(connection)

    with tenant_transaction(
        engine,
        workspace_id="WS-tenant",
        user_id="USR-user",
    ) as yielded:
        assert yielded is connection
        assert engine.entered is True
        assert len(connection.calls) == 1

    assert engine.exited is True


def test_sqlite_compatibility_validates_context_without_setting_session_variables():
    engine = create_engine("sqlite:///:memory:")
    try:
        with tenant_transaction(
            engine,
            workspace_id="WS-local",
            user_id="USR-local",
        ) as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()


def test_rls_current_setting_expressions_are_fail_closed_when_unset():
    assert CURRENT_WORKSPACE_SQL == (
        "NULLIF(current_setting('app.current_workspace_id', true), '')"
    )
    assert CURRENT_USER_SQL == "NULLIF(current_setting('app.current_user_id', true), '')"
    assert ", true" in CURRENT_WORKSPACE_SQL
    assert ", true" in CURRENT_USER_SQL
