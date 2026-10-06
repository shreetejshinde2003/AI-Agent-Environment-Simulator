"""Phase 4.5.1 tenant-boundary inventory and isolation-contract tests."""

from app.security.tenant_isolation import (
    IsolationScope,
    TABLE_ISOLATION_RULES,
    tenant_owned_tables,
)
from app.storage import models as dbm


def test_every_persisted_table_has_an_explicit_isolation_classification():
    persisted = set(dbm.metadata.tables)
    classified = set(TABLE_ISOLATION_RULES)

    assert classified == persisted


def test_direct_tenant_tables_have_real_workspace_columns():
    for rule in TABLE_ISOLATION_RULES.values():
        if rule.scope not in {
            IsolationScope.WORKSPACE_ROOT,
            IsolationScope.TENANT_DIRECT,
        }:
            continue

        assert rule.workspace_column is not None
        table = dbm.metadata.tables[rule.table]
        assert rule.workspace_column in table.c


def test_simulation_derived_tables_are_joinable_to_the_workspace_root():
    expected = {
        "tasks",
        "agent_executions",
        "agent_messages",
        "activity_events",
        "run_events",
        "simulation_metrics",
        "simulation_uploads",
    }
    actual = {
        rule.table
        for rule in TABLE_ISOLATION_RULES.values()
        if rule.scope == IsolationScope.TENANT_VIA_SIMULATION
    }

    assert actual == expected

    for table_name in expected:
        rule = TABLE_ISOLATION_RULES[table_name]
        assert rule.parent_table == "simulations"
        assert rule.parent_column == "simulation_id"
        assert "simulation_id" in dbm.metadata.tables[table_name].c


def test_uploads_are_direct_tenant_owned_after_v9_hardening():
    rule = TABLE_ISOLATION_RULES["uploads"]
    assert rule.scope == IsolationScope.TENANT_DIRECT
    assert rule.workspace_column == "workspace_id"
    assert "workspace_id" in dbm.uploads.c
    assert "created_by_user_id" in dbm.uploads.c
    assert dbm.uploads.c.workspace_id.nullable
    assert dbm.uploads.c.created_by_user_id.nullable


def test_global_and_identity_tables_are_not_mistaken_for_tenant_business_data():
    assert TABLE_ISOLATION_RULES["schema_version"].scope == IsolationScope.SYSTEM_GLOBAL
    assert TABLE_ISOLATION_RULES["dataset_registry"].scope == IsolationScope.SYSTEM_GLOBAL
    assert TABLE_ISOLATION_RULES["agent_roster"].scope == IsolationScope.SYSTEM_GLOBAL
    assert TABLE_ISOLATION_RULES["users"].scope == IsolationScope.IDENTITY
    assert TABLE_ISOLATION_RULES["auth_sessions"].scope == IsolationScope.IDENTITY


def test_tenant_owned_inventory_contains_root_direct_indirect_and_pending_tables():
    assert tenant_owned_tables() == {
        "workspaces",
        "organization_memberships",
        "organization_human_role_assignments",
        "simulations",
        "tasks",
        "agent_executions",
        "agent_messages",
        "activity_events",
        "run_events",
        "simulation_metrics",
        "simulation_uploads",
        "uploads",
        "custom_agents",
        "custom_agent_revisions",
        "hr_requirements", "hr_requirements_revisions",
        "hr_role_knowledge", "hr_role_knowledge_revisions",
        "hr_job_descriptions", "hr_job_descriptions_revisions",
        "hr_review_submissions", "hr_review_events",
    }
