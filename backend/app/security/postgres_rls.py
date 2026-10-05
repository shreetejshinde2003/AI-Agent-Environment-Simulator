"""PostgreSQL row-level security policy definitions for tenant-owned data.

Phase 4.5.5B activates HR-role isolation alongside bootstrap and simulation RLS.
Uploads still require schema hardening and are deliberately excluded.
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
WRITE_POLICY_NAME = "fm_tenant_isolation_write"


@dataclass(frozen=True, slots=True)
class PostgresRLSPolicy:
    table: str
    using_sql: str
    check_sql: str
    write_using_sql: str | None = None
    write_check_sql: str | None = None

    @property
    def policy_names(self) -> frozenset[str]:
        return frozenset({POLICY_NAME, WRITE_POLICY_NAME} if self.write_using_sql else {POLICY_NAME})

    def ddl(self) -> tuple[str, ...]:
        statements = (
            f'ALTER TABLE "{self.table}" ENABLE ROW LEVEL SECURITY',
            f'ALTER TABLE "{self.table}" FORCE ROW LEVEL SECURITY',
            f'DROP POLICY IF EXISTS "{POLICY_NAME}" ON "{self.table}"',
        )
        if self.write_using_sql is not None:
            # SELECT-only policy must not accidentally grant DELETE privileges.
            # The managerial ALL policy covers INSERT/UPDATE/DELETE and adds no
            # broader SELECT access than managers already receive.
            return statements + (
                f'DROP POLICY IF EXISTS "{WRITE_POLICY_NAME}" ON "{self.table}"',
                f'CREATE POLICY "{POLICY_NAME}" ON "{self.table}" FOR SELECT USING ({self.using_sql})',
                f'CREATE POLICY "{WRITE_POLICY_NAME}" ON "{self.table}" FOR ALL '
                f'USING ({self.write_using_sql}) WITH CHECK ({self.write_check_sql})',
            )
        return statements + (
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


def _human_role_policy() -> PostgresRLSPolicy:
    table = "organization_human_role_assignments"
    actor = (
        "EXISTS (SELECT 1 FROM organization_memberships AS hr_actor "
        f"WHERE hr_actor.workspace_id = {table}.workspace_id "
        f"AND hr_actor.user_id = {CURRENT_USER_SQL} AND hr_actor.active = TRUE"
    )
    base = (
        f"{CURRENT_USER_SQL} IS NOT NULL AND workspace_id = {CURRENT_WORKSPACE_SQL} AND "
        "EXISTS (SELECT 1 FROM workspaces AS hr_workspace "
        f"WHERE hr_workspace.id = {table}.workspace_id "
        "AND hr_workspace.kind = 'organization' AND hr_workspace.active = TRUE)"
    )
    manager = f"({base}) AND {actor} AND hr_actor.membership_role IN ('owner', 'admin'))"
    visible = (
        f"({manager}) OR (({base}) AND user_id = {CURRENT_USER_SQL} AND active = TRUE "
        f"AND {actor} AND hr_actor.membership_role IN ('owner', 'admin', 'member')))"
    )
    writable = (
        f"({manager}) AND assigned_by_user_id = {CURRENT_USER_SQL} AND (active = FALSE OR "
        "EXISTS (SELECT 1 FROM organization_memberships AS hr_target "
        f"WHERE hr_target.workspace_id = {table}.workspace_id "
        f"AND hr_target.user_id = {table}.user_id AND hr_target.active = TRUE))"
    )
    return PostgresRLSPolicy(table, visible, writable, manager, writable)


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
            elif rule.table == "organization_human_role_assignments":
                policies.append(_human_role_policy())
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
HR_ROLE_RLS_TABLES = frozenset({"organization_human_role_assignments"})
UPLOAD_RLS_TABLES = frozenset({"uploads"})
ACTIVE_RLS_TABLES = (
    DATA_PLANE_RLS_TABLES
    | BOOTSTRAP_RLS_TABLES
    | HR_ROLE_RLS_TABLES
    | UPLOAD_RLS_TABLES
)
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

    Historical entrypoint name retained: includes bootstrap, HR roles and the
    eight simulation data-plane tables. Upload ownership remains deferred.
    Unknown policies can OR together with our permissive policy. Refuse them,
    rather than weakening the boundary or deleting operator-owned DDL. Unassigned
    legacy history must be explicitly migrated before first activation.
    """
    if connection.dialect.name != "postgresql":
        return
    require_rls_runtime_role(connection)
    policies_by_table = {policy.table: policy for policy in POSTGRES_RLS_POLICIES}
    states = {}
    for table in sorted(POSTGRES_RLS_TABLES):
        state = connection.execute(text(
            "SELECT c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c WHERE c.oid = to_regclass(:table)"
        ), {"table": table}).mappings().one()
        states[table] = state
        if table in DEFERRED_RLS_TABLES and state["relrowsecurity"]:
            raise RuntimeError(
                f"RLS on {table} requires its tenant-readiness checkpoint."
            )
        if table in ACTIVE_RLS_TABLES:
            names = connection.execute(text(
                "SELECT polname FROM pg_policy WHERE polrelid = to_regclass(:table)"
            ), {"table": table}).scalars().all()
            if set(names) - policies_by_table[table].policy_names:
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

    if not states["uploads"]["relrowsecurity"]:
        unresolved_uploads = connection.execute(text(
            "SELECT EXISTS (SELECT 1 FROM uploads WHERE workspace_id IS NULL)"
        )).scalar_one()
        if unresolved_uploads:
            raise RuntimeError(
                "Legacy uploads have no workspace ownership. Back up and explicitly "
                "resolve or remove them before activating upload RLS."
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
    preflighted install_data_plane_rls_policies instead. This full-set installer
    bypasses readiness preflight and is not the application startup path.
    """

    if connection.dialect.name != "postgresql":
        return

    for statement in postgres_rls_ddl():
        connection.exec_driver_sql(statement)
