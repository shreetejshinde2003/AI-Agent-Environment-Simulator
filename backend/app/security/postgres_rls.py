"""PostgreSQL row-level security policy definitions for tenant-owned data.

Phase 4.5.3 defines the complete policy contract. Phase 4.5.4C activates only
the simulation data plane; bootstrap and HR-role tables remain deferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy import text

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

# Explicit readiness allowlist: newly classified tables are not auto-activated.
DATA_PLANE_RLS_TABLES = frozenset({
    "simulations", "tasks", "agent_executions", "agent_messages",
    "activity_events", "run_events", "simulation_metrics", "simulation_uploads",
})
DEFERRED_RLS_TABLES = POSTGRES_RLS_TABLES - DATA_PLANE_RLS_TABLES


def require_rls_runtime_role(connection) -> None:
    """Reject credentials that FORCE RLS cannot constrain (including RESET ROLE)."""
    if connection.dialect.name != "postgresql":
        return
    unsafe = connection.execute(text(
        "SELECT EXISTS (SELECT 1 FROM pg_roles "
        "WHERE (rolname IN (current_user, session_user) "
        "OR pg_has_role(session_user, oid, 'MEMBER')) "
        "AND (rolsuper OR rolbypassrls))"
    )).scalar_one()
    if unsafe:
        raise RuntimeError(
            "PostgreSQL application credentials must be NOSUPERUSER NOBYPASSRLS "
            "with no membership in bypass-capable roles. "
            "Data-plane RLS activation refused; use a non-bypass application role."
        )


def install_data_plane_rls_policies(connection) -> None:
    """Preflight and activate the ready subset inside initialization's transaction.

    Unknown policies can OR together with our permissive policy. Refuse them,
    rather than weakening the boundary or deleting operator-owned DDL. Unassigned
    legacy history must be explicitly migrated before first activation.
    """
    if connection.dialect.name != "postgresql":
        return
    require_rls_runtime_role(connection)
    states = {}
    for table in sorted(POSTGRES_RLS_TABLES):
        state = connection.execute(text(
            "SELECT c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c WHERE c.oid = to_regclass(:table)"
        ), {"table": table}).mappings().one()
        states[table] = state
        if table in DEFERRED_RLS_TABLES and state["relrowsecurity"]:
            raise RuntimeError(
                f"RLS on {table} requires a bootstrap/HR-role readiness checkpoint."
            )
        if table in DATA_PLANE_RLS_TABLES:
            names = connection.execute(text(
                "SELECT polname FROM pg_policy WHERE polrelid = to_regclass(:table)"
            ), {"table": table}).scalars().all()
            if set(names) - {POLICY_NAME}:
                raise RuntimeError(f"Unreviewed PostgreSQL RLS policies on {table}.")

    if not states["simulations"]["relrowsecurity"]:
        unassigned = connection.execute(text(
            "SELECT EXISTS (SELECT 1 FROM simulations WHERE workspace_id IS NULL)"
        )).scalar_one()
        if unassigned:
            raise RuntimeError(
                "Legacy simulations have no workspace ownership. Back up and "
                "explicitly assign their workspace before activating data-plane RLS."
            )

    for policy in POSTGRES_RLS_POLICIES:
        if policy.table in DATA_PLANE_RLS_TABLES:
            for statement in policy.ddl():
                connection.exec_driver_sql(statement)


def postgres_rls_ddl() -> tuple[str, ...]:
    return tuple(statement for policy in POSTGRES_RLS_POLICIES for statement in policy.ddl())


def install_postgres_rls_policies(connection) -> None:
    """Install/refresh all declared RLS policies on a PostgreSQL connection.

    Definition/testing utility only: repository startup uses the narrower,
    preflighted install_data_plane_rls_policies instead. Do not use this full-set
    installer before bootstrap and HR-role context are ready.
    """

    if connection.dialect.name != "postgresql":
        return

    for statement in postgres_rls_ddl():
        connection.exec_driver_sql(statement)
