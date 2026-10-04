"""PostgreSQL row-level security policy definitions for tenant-owned data.

Phase 4.5.3 defines the complete RLS DDL contract but deliberately does not
install it during repository startup yet. Repository operations still need to be
moved onto tenant-scoped transactions in Phase 4.5.4 before FORCE ROW LEVEL
SECURITY can be enabled safely in production.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.security.tenant_db_context import CURRENT_USER_SQL, CURRENT_WORKSPACE_SQL
from app.security.tenant_isolation import IsolationScope, TABLE_ISOLATION_RULES

POLICY_NAME = "fm_tenant_isolation"


@dataclass(frozen=True, slots=True)
class PostgresRLSPolicy:
    table: str
    using_sql: str
    check_sql: str

    def ddl(self) -> tuple[str, ...]:
        return (
            f'ALTER TABLE "{self.table}" ENABLE ROW LEVEL SECURITY',
            f'ALTER TABLE "{self.table}" FORCE ROW LEVEL SECURITY',
            f'DROP POLICY IF EXISTS "{POLICY_NAME}" ON "{self.table}"',
            (
                f'CREATE POLICY "{POLICY_NAME}" ON "{self.table}" '
                f'FOR ALL USING ({self.using_sql}) WITH CHECK ({self.check_sql})'
            ),
        )


def _workspace_root_policy() -> PostgresRLSPolicy:
    # Selected-workspace access is the normal path. The user clauses are the
    # bootstrap path required for Personal Workspace and organization discovery.
    visible = (
        f"id = {CURRENT_WORKSPACE_SQL} OR "
        f"personal_owner_user_id = {CURRENT_USER_SQL} OR "
        "EXISTS ("
        "SELECT 1 FROM organization_memberships AS om "
        "WHERE om.workspace_id = workspaces.id "
        f"AND om.user_id = {CURRENT_USER_SQL} AND om.active = TRUE"
        ")"
    )
    writable = (
        f"id = {CURRENT_WORKSPACE_SQL} OR "
        f"personal_owner_user_id = {CURRENT_USER_SQL} OR "
        f"created_by_user_id = {CURRENT_USER_SQL}"
    )
    return PostgresRLSPolicy("workspaces", visible, writable)


def _membership_policy() -> PostgresRLSPolicy:
    # A user may read their own membership rows during workspace discovery.
    # Writes remain selected-workspace scoped.
    visible = (
        f"workspace_id = {CURRENT_WORKSPACE_SQL} OR "
        f"user_id = {CURRENT_USER_SQL}"
    )
    writable = f"workspace_id = {CURRENT_WORKSPACE_SQL}"
    return PostgresRLSPolicy("organization_memberships", visible, writable)


def _direct_policy(table: str, workspace_column: str) -> PostgresRLSPolicy:
    predicate = f"{workspace_column} = {CURRENT_WORKSPACE_SQL}"
    return PostgresRLSPolicy(table, predicate, predicate)


def _simulation_child_policy(table: str, simulation_column: str) -> PostgresRLSPolicy:
    predicate = (
        "EXISTS ("
        "SELECT 1 FROM simulations AS tenant_simulation "
        f"WHERE tenant_simulation.id = {table}.{simulation_column} "
        f"AND tenant_simulation.workspace_id = {CURRENT_WORKSPACE_SQL}"
        ")"
    )
    return PostgresRLSPolicy(table, predicate, predicate)


def build_postgres_rls_policies() -> tuple[PostgresRLSPolicy, ...]:
    """Build RLS policies from the central tenant-isolation contract.

    ``uploads`` is intentionally excluded until it gains explicit tenant/user
    ownership. System-global and identity tables are outside workspace RLS.
    """

    policies: list[PostgresRLSPolicy] = []
    for rule in TABLE_ISOLATION_RULES.values():
        if rule.scope == IsolationScope.WORKSPACE_ROOT:
            policies.append(_workspace_root_policy())
        elif rule.scope == IsolationScope.TENANT_DIRECT:
            if rule.table == "organization_memberships":
                policies.append(_membership_policy())
            else:
                assert rule.workspace_column is not None
                policies.append(_direct_policy(rule.table, rule.workspace_column))
        elif rule.scope == IsolationScope.TENANT_VIA_SIMULATION:
            assert rule.parent_column is not None
            policies.append(_simulation_child_policy(rule.table, rule.parent_column))

    return tuple(policies)


POSTGRES_RLS_POLICIES = build_postgres_rls_policies()
POSTGRES_RLS_TABLES = frozenset(policy.table for policy in POSTGRES_RLS_POLICIES)


def postgres_rls_ddl() -> tuple[str, ...]:
    return tuple(statement for policy in POSTGRES_RLS_POLICIES for statement in policy.ddl())


def install_postgres_rls_policies(connection) -> None:
    """Install/refresh all declared RLS policies on a PostgreSQL connection.

    This function is intentionally explicit rather than called from repository
    initialization in Phase 4.5.3. Enabling FORCE RLS before repository queries
    carry trusted tenant context would break legitimate requests. Phase 4.5.4
    wires tenant-aware repository transactions first, after which this installer
    can be activated safely.
    """

    if connection.dialect.name != "postgresql":
        return

    for statement in postgres_rls_ddl():
        connection.exec_driver_sql(statement)
