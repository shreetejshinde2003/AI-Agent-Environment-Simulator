"""Phase 4.5.3 PostgreSQL RLS policy-contract tests."""

from types import SimpleNamespace

from app.security.postgres_rls import (
    POLICY_NAME,
    POSTGRES_RLS_POLICIES,
    POSTGRES_RLS_TABLES,
    install_postgres_rls_policies,
    postgres_rls_ddl,
)
from app.security.tenant_isolation import IsolationScope, TABLE_ISOLATION_RULES


def test_rls_covers_every_current_workspace_owned_table_including_uploads():
    expected = {
        rule.table
        for rule in TABLE_ISOLATION_RULES.values()
        if rule.scope
        in {
            IsolationScope.WORKSPACE_ROOT,
            IsolationScope.TENANT_DIRECT,
            IsolationScope.TENANT_VIA_SIMULATION,
        }
    }
    assert POSTGRES_RLS_TABLES == expected
    assert "uploads" in POSTGRES_RLS_TABLES


def test_every_rls_table_enables_and_forces_row_level_security():
    ddl = postgres_rls_ddl()
    for table in POSTGRES_RLS_TABLES:
        assert f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY' in ddl
        assert f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY' in ddl
        assert f'DROP POLICY IF EXISTS "{POLICY_NAME}" ON "{table}"' in ddl


def test_direct_tenant_policies_compare_against_transaction_workspace_context():
    policies = {policy.table: policy for policy in POSTGRES_RLS_POLICIES}
    for table in (
        "organization_human_role_assignments",
        "simulations",
        "uploads",
    ):
        policy = policies[table]
        assert "current_setting('app.current_workspace_id', true)" in policy.using_sql
        assert "current_setting('app.current_workspace_id', true)" in policy.check_sql
        assert "workspace_id =" in policy.using_sql


def test_simulation_children_resolve_tenancy_through_parent_simulation():
    policies = {policy.table: policy for policy in POSTGRES_RLS_POLICIES}
    children = {
        "tasks",
        "agent_executions",
        "agent_messages",
        "activity_events",
        "run_events",
        "simulation_metrics",
        "simulation_uploads",
    }
    for table in children:
        sql = policies[table].using_sql
        assert "EXISTS (" in sql
        assert "FROM simulations AS tenant_simulation" in sql
        assert f"tenant_simulation.id = {table}.simulation_id" in sql
        assert "tenant_simulation.workspace_id" in sql
        assert "app.current_workspace_id" in sql


def test_workspace_and_membership_bootstrap_paths_are_user_bound():
    policies = {policy.table: policy for policy in POSTGRES_RLS_POLICIES}
    workspace = policies["workspaces"]
    membership = policies["organization_memberships"]

    assert "personal_owner_user_id" in workspace.using_sql
    assert "organization_memberships" in workspace.using_sql
    assert "app.current_user_id" in workspace.using_sql
    assert "user_id =" in membership.using_sql
    assert "app.current_user_id" in membership.using_sql
    assert "workspace_id =" in membership.check_sql


def test_policy_ddl_is_fail_closed_and_does_not_embed_a_fallback_tenant():
    sql = "\n".join(postgres_rls_ddl())
    assert "current_setting('app.current_workspace_id', true)" in sql
    assert "current_setting('app.current_user_id', true)" in sql
    assert "COALESCE" not in sql.upper()
    assert "DEFAULT" not in sql.upper()


class RecordingConnection:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self):
        self.statements = []

    def exec_driver_sql(self, statement):
        self.statements.append(statement)


def test_installer_is_postgres_only_and_executes_the_complete_policy_set():
    postgres = RecordingConnection()
    install_postgres_rls_policies(postgres)
    assert tuple(postgres.statements) == postgres_rls_ddl()

    sqlite = RecordingConnection()
    sqlite.dialect = SimpleNamespace(name="sqlite")
    install_postgres_rls_policies(sqlite)
    assert sqlite.statements == []
