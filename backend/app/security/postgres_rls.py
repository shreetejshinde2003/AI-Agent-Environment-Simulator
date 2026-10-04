"""PostgreSQL row-level security policy definitions for tenant-owned data.

Phase 4.5.5A activates user-bound bootstrap alongside the simulation data plane.
HR-role tables remain deferred; uploads still require schema hardening.
"""

from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy import text

from app.security.tenant_db_context import (
    CURRENT_USER_SQL, CURRENT_WORKSPACE_SQL, INVITATION_DIGEST_SQL,
    INVITATION_WORKSPACE_SQL, RECOVERY_OWNER_SQL, STARTUP_RECOVERY_PRINCIPAL,
)
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
    # Membership policy never queries workspaces: avoid recursive RLS expansion.
    visible = (
        f"{CURRENT_USER_SQL} IS NOT NULL AND ("
        f"id = {CURRENT_WORKSPACE_SQL} OR "
        f"({CURRENT_WORKSPACE_SQL} IS NULL AND ("
        f"(active = TRUE AND kind = 'personal' AND personal_owner_user_id = {CURRENT_USER_SQL}) OR "
        "(active = TRUE AND kind = 'organization' AND EXISTS ("
        "SELECT 1 FROM organization_memberships AS om "
        "WHERE om.workspace_id = workspaces.id "
        f"AND om.user_id = {CURRENT_USER_SQL} AND om.active = TRUE"
        ")) OR "
        f"(active = TRUE AND kind = 'organization' AND join_code_digest = {INVITATION_DIGEST_SQL}) OR "
        f"({CURRENT_USER_SQL} = '{STARTUP_RECOVERY_PRINCIPAL}' AND "
        f"(created_by_user_id = {RECOVERY_OWNER_SQL} OR personal_owner_user_id = {RECOVERY_OWNER_SQL}))"
        ")))"
    )
    writable = (
        f"{CURRENT_USER_SQL} IS NOT NULL AND (id = {CURRENT_WORKSPACE_SQL} OR "
        f"({CURRENT_WORKSPACE_SQL} IS NULL AND active = TRUE AND "
        f"created_by_user_id = {CURRENT_USER_SQL} AND "
        f"((kind = 'personal' AND personal_owner_user_id = {CURRENT_USER_SQL}) OR "
        "(kind = 'organization' AND personal_owner_user_id IS NULL))))"
    )
    return PostgresRLSPolicy("workspaces", visible, writable)


def _membership_policy() -> PostgresRLSPolicy:
    # Discovery exposes only active own memberships. Invitation access permits
    # own inactive rows for reactivation, not other members or a selected tenant.
    visible = (
        f"{CURRENT_USER_SQL} IS NOT NULL AND (workspace_id = {CURRENT_WORKSPACE_SQL} OR "
        f"({CURRENT_WORKSPACE_SQL} IS NULL AND ((user_id = {CURRENT_USER_SQL} AND active = TRUE) OR "
        f"(user_id = {CURRENT_USER_SQL} AND workspace_id = {INVITATION_WORKSPACE_SQL}))))"
    )
    writable = (
        f"{CURRENT_USER_SQL} IS NOT NULL AND (workspace_id = {CURRENT_WORKSPACE_SQL} OR "
        f"(workspace_id = {INVITATION_WORKSPACE_SQL} AND user_id = {CURRENT_USER_SQL} "
        f"AND added_by_user_id = {CURRENT_USER_SQL} AND active = TRUE))"
    )
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
BOOTSTRAP_RLS_TABLES = frozenset({"workspaces", "organization_memberships"})
ACTIVE_RLS_TABLES = DATA_PLANE_RLS_TABLES | BOOTSTRAP_RLS_TABLES
DEFERRED_RLS_TABLES = POSTGRES_RLS_TABLES - ACTIVE_RLS_TABLES


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

    Historical entrypoint name retained: the subset now includes the two ready
    bootstrap tables as well as the eight simulation data-plane tables.
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
                f"RLS on {table} requires an HR-role readiness checkpoint."
            )
        if table in ACTIVE_RLS_TABLES:
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
        if policy.table in ACTIVE_RLS_TABLES:
            for statement in policy.ddl():
                connection.exec_driver_sql(statement)


def postgres_rls_ddl() -> tuple[str, ...]:
    return tuple(statement for policy in POSTGRES_RLS_POLICIES for statement in policy.ddl())


def install_postgres_rls_policies(connection) -> None:
    """Install/refresh all declared RLS policies on a PostgreSQL connection.

    Definition/testing utility only: repository startup uses the narrower,
    preflighted install_data_plane_rls_policies instead. Do not use this full-set
    installer before HR-role context is ready.
    """

    if connection.dialect.name != "postgresql":
        return

    for statement in postgres_rls_ddl():
        connection.exec_driver_sql(statement)
