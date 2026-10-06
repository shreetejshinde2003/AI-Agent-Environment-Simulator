"""Tenant-isolation contract used to drive Phase 4.5 hardening.

This module is intentionally declarative. It classifies every persisted table by
how tenant ownership is determined so PostgreSQL RLS and repository safeguards
can be implemented from one explicit contract instead of scattered assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IsolationScope(str, Enum):
    SYSTEM_GLOBAL = "system_global"
    IDENTITY = "identity"
    WORKSPACE_ROOT = "workspace_root"
    TENANT_DIRECT = "tenant_direct"
    TENANT_VIA_SIMULATION = "tenant_via_simulation"
    REQUIRES_SCHEMA_HARDENING = "requires_schema_hardening"


@dataclass(frozen=True)
class TableIsolationRule:
    table: str
    scope: IsolationScope
    workspace_column: str | None = None
    parent_table: str | None = None
    parent_column: str | None = None
    notes: str = ""


TABLE_ISOLATION_RULES: dict[str, TableIsolationRule] = {
    "schema_version": TableIsolationRule(
        "schema_version",
        IsolationScope.SYSTEM_GLOBAL,
        notes="Database migration metadata; never tenant business data.",
    ),
    "users": TableIsolationRule(
        "users",
        IsolationScope.IDENTITY,
        notes="Application identity record; authorization is user-bound, not workspace-owned.",
    ),
    "auth_sessions": TableIsolationRule(
        "auth_sessions",
        IsolationScope.IDENTITY,
        parent_table="users",
        parent_column="user_id",
        notes="Opaque application sessions are scoped to one authenticated user.",
    ),
    "workspaces": TableIsolationRule(
        "workspaces",
        IsolationScope.WORKSPACE_ROOT,
        workspace_column="id",
        notes="Root boundary for Personal Workspaces and Organizations.",
    ),
    "organization_memberships": TableIsolationRule(
        "organization_memberships",
        IsolationScope.TENANT_DIRECT,
        workspace_column="workspace_id",
    ),
    "organization_human_role_assignments": TableIsolationRule(
        "organization_human_role_assignments",
        IsolationScope.TENANT_DIRECT,
        workspace_column="workspace_id",
    ),
    "dataset_registry": TableIsolationRule(
        "dataset_registry",
        IsolationScope.SYSTEM_GLOBAL,
        notes="Shared benchmark registry, not organization-owned data.",
    ),
    "simulations": TableIsolationRule(
        "simulations",
        IsolationScope.TENANT_DIRECT,
        workspace_column="workspace_id",
        notes="Primary tenant-owned execution record.",
    ),
    "tasks": TableIsolationRule(
        "tasks",
        IsolationScope.TENANT_VIA_SIMULATION,
        parent_table="simulations",
        parent_column="simulation_id",
    ),
    "agent_executions": TableIsolationRule(
        "agent_executions",
        IsolationScope.TENANT_VIA_SIMULATION,
        parent_table="simulations",
        parent_column="simulation_id",
    ),
    "agent_messages": TableIsolationRule(
        "agent_messages",
        IsolationScope.TENANT_VIA_SIMULATION,
        parent_table="simulations",
        parent_column="simulation_id",
    ),
    "activity_events": TableIsolationRule(
        "activity_events",
        IsolationScope.TENANT_VIA_SIMULATION,
        parent_table="simulations",
        parent_column="simulation_id",
    ),
    "run_events": TableIsolationRule(
        "run_events",
        IsolationScope.TENANT_VIA_SIMULATION,
        parent_table="simulations",
        parent_column="simulation_id",
    ),
    "simulation_metrics": TableIsolationRule(
        "simulation_metrics",
        IsolationScope.TENANT_VIA_SIMULATION,
        parent_table="simulations",
        parent_column="simulation_id",
    ),
    "simulation_uploads": TableIsolationRule(
        "simulation_uploads",
        IsolationScope.TENANT_VIA_SIMULATION,
        parent_table="simulations",
        parent_column="simulation_id",
        notes="Join rows inherit the workspace of their simulation.",
    ),
    "uploads": TableIsolationRule(
        "uploads",
        IsolationScope.TENANT_DIRECT,
        workspace_column="workspace_id",
        notes=(
            "V9 explicit workspace ownership is API-scoped and ready for direct PostgreSQL RLS. "
            "Startup refuses first activation while unresolved legacy workspace ownership remains."
        ),
    ),
    "custom_agents": TableIsolationRule("custom_agents", IsolationScope.TENANT_DIRECT, workspace_column="workspace_id"),
    "custom_agent_revisions": TableIsolationRule("custom_agent_revisions", IsolationScope.TENANT_DIRECT, workspace_column="workspace_id"),
    **{name: TableIsolationRule(name, IsolationScope.TENANT_DIRECT, workspace_column="workspace_id")
       for family in ("requirements", "role_knowledge", "job_descriptions")
       for name in ("hr_" + family, "hr_" + family + "_revisions")},
    **{name: TableIsolationRule(name, IsolationScope.TENANT_DIRECT, workspace_column="workspace_id")
       for name in ("hr_review_submissions", "hr_review_events")},
    "agent_roster": TableIsolationRule(
        "agent_roster",
        IsolationScope.SYSTEM_GLOBAL,
        notes="Historical global display metadata; executable configuration uses tenant-owned custom_agents.",
    ),
}


def rules_for(scope: IsolationScope) -> tuple[TableIsolationRule, ...]:
    return tuple(rule for rule in TABLE_ISOLATION_RULES.values() if rule.scope == scope)


def tenant_owned_tables() -> frozenset[str]:
    return frozenset(
        rule.table
        for rule in TABLE_ISOLATION_RULES.values()
        if rule.scope
        in {
            IsolationScope.WORKSPACE_ROOT,
            IsolationScope.TENANT_DIRECT,
            IsolationScope.TENANT_VIA_SIMULATION,
            IsolationScope.REQUIRES_SCHEMA_HARDENING,
        }
    )
