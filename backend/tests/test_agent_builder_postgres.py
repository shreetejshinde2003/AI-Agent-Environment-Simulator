"""Isolated non-bypass local PostgreSQL security and persistence acceptance."""
import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.exc import DBAPIError

from app.models.schemas import CustomAgentConfig, StageExecution, TaskExecutionMode, TaskStatus
from app.agents.llm_client import LLMResponse
from app.security.rbac import AuthorizationError
from app.security.tenant_db_context import tenant_transaction
from app.storage import models as dbm
from app.storage.custom_agents import AgentBuilderError
from app.storage.database import SCHEMA_VERSION
from test_postgres_data_plane_integration import pg_repo, seed
from test_simulation_workspace_api import completed_task


def config(**kwargs):
    return CustomAgentConfig(name="Reviewer", purpose="Review text", instructions="Summarize", **kwargs)


def scope(repo, user="USR-a"):
    return dict(workspace_id=repo.get_personal_workspace(user)["id"], user_id=user)


def test_live_definitions_revisions_force_rls_and_tenant_denial(pg_repo):
    a, b = scope(pg_repo), scope(pg_repo, "USR-b")
    agent = pg_repo.save_custom_agent(config(), **a)
    assert pg_repo.get_custom_agent(agent.id, **a) == agent
    # Same name permitted in another tenant; never shared.
    other = pg_repo.save_custom_agent(config(), **b)
    assert other.id != agent.id
    for table in (dbm.custom_agents, dbm.custom_agent_revisions):
        with pg_repo.engine.connect() as connection:
            assert connection.execute(select(table)).all() == []
            row = connection.execute(text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid=to_regclass(:name)"), {"name": table.name}).one()
            assert tuple(row) == (True, True)
        with tenant_transaction(pg_repo.engine, **b) as connection:
            key = table.c.id if table is dbm.custom_agents else table.c.agent_id
            assert connection.execute(select(table).where(key == agent.id)).all() == []
            assert connection.execute(update(table).where(key == agent.id).values(workspace_id=b["workspace_id"])).rowcount == 0
            assert connection.execute(delete(table).where(key == agent.id)).rowcount == 0
    with pytest.raises(AgentBuilderError) as absent:
        pg_repo.get_custom_agent(agent.id, **b)
    assert absent.value.status_code == 404
    with pytest.raises(AuthorizationError):
        pg_repo.get_custom_agent(agent.id, workspace_id=a["workspace_id"], user_id="USR-b")
    with pytest.raises(DBAPIError):
        with tenant_transaction(pg_repo.engine, **b) as connection:
            connection.execute(insert(dbm.custom_agent_revisions).values(agent_id=agent.id, workspace_id=a["workspace_id"],
                revision=2, updated_by_user_id="USR-b", updated_at=agent.updated_at.isoformat(), config_hash=agent.config_hash,
                resolved_model=agent.resolved_model, payload=agent.config.model_dump(mode="json")))
    updated = pg_repo.save_custom_agent(config(active=False), agent_id=agent.id, expected_revision=1, **a)
    assert updated.revision == 2
    assert [v.revision for v in pg_repo.custom_agent_revisions(agent.id, **a)] == [1, 2]
    with tenant_transaction(pg_repo.engine, **a) as connection:
        # Even a manager cannot rewrite or delete the saved execution config.
        assert connection.execute(update(dbm.custom_agent_revisions).values(config_hash="bad")).rowcount == 0
        assert connection.execute(delete(dbm.custom_agent_revisions)).rowcount == 0


def test_live_member_manager_inactive_enforcement_in_repository_and_rls(pg_repo):
    org, code = pg_repo.create_organization(creator_user_id="USR-a", name="Builder security")
    pg_repo.join_organization(user_id="USR-b", join_code=code)
    owner = dict(workspace_id=org["id"], user_id="USR-a")
    member = dict(workspace_id=org["id"], user_id="USR-b")
    agent = pg_repo.save_custom_agent(config(), **owner)
    assert pg_repo.get_custom_agent(agent.id, for_execution=True, **member).id == agent.id
    with pytest.raises(AuthorizationError):
        pg_repo.save_custom_agent(config(), **member)
    with tenant_transaction(pg_repo.engine, **member) as connection:
        assert connection.execute(update(dbm.custom_agents).values(active=False)).rowcount == 0
    with pytest.raises(DBAPIError):
        with tenant_transaction(pg_repo.engine, **member) as connection:
            connection.execute(insert(dbm.custom_agent_revisions).values(agent_id=agent.id, workspace_id=org["id"], revision=2,
                updated_by_user_id="USR-b", updated_at=agent.updated_at.isoformat(), config_hash=agent.config_hash,
                resolved_model=agent.resolved_model, payload=agent.config.model_dump(mode="json")))
    pg_repo.change_organization_membership_role(workspace_id=org["id"], target_user_id="USR-b", actor_user_id="USR-a", new_role="admin")
    assert pg_repo.save_custom_agent(config(), agent_id=agent.id, expected_revision=1, **member).revision == 2
    pg_repo.deactivate_organization_membership(workspace_id=org["id"], target_user_id="USR-b", actor_user_id="USR-a")
    with pytest.raises(AuthorizationError):
        pg_repo.list_custom_agents(**member)
    # Raw tenant settings do not override inactive membership for builder tables.
    with tenant_transaction(pg_repo.engine, **member) as connection:
        assert connection.execute(select(dbm.custom_agents)).all() == []
        assert connection.execute(select(dbm.custom_agent_revisions)).all() == []


def test_live_v10_additive_migration_preserves_existing_evidence(pg_repo):
    task = seed(pg_repo, "T-v10-builder", "USR-a")
    before = pg_repo.get_for_tenant(task.id, **scope(pg_repo)).model_dump(mode="json")
    # Only fixture-owned schema; this recreates the actual pre-builder inventory.
    with pg_repo.engine.begin() as connection:
        dbm.custom_agent_revisions.drop(connection)
        dbm.custom_agents.drop(connection)
        connection.execute(update(dbm.schema_version).values(version=10))
    pg_repo.initialize()
    pg_repo.initialize()
    assert pg_repo.get_for_tenant(task.id, **scope(pg_repo)).model_dump(mode="json") == before
    with pg_repo.engine.connect() as connection:
        assert connection.execute(select(dbm.schema_version.c.version)).scalar_one() == SCHEMA_VERSION
    pg_repo.save_custom_agent(config(), **scope(pg_repo))


def test_live_custom_execution_persists_stage_and_recycle_evidence(pg_repo, monkeypatch):
    from app.api.routes import tasks
    identity = scope(pg_repo)
    monkeypatch.setattr(tasks, "repository", pg_repo)
    monkeypatch.setattr("app.api.routes.simulation.repository", pg_repo)
    monkeypatch.setattr("app.api.routes.messages.repository", pg_repo)
    provider = AsyncMock(return_value=LLMResponse("Persistent provider output", 10, 5, .01, "fixture-model"))
    monkeypatch.setattr("app.agents.llm_client.call_llm", provider)
    agent = pg_repo.save_custom_agent(config(), **identity)
    task = completed_task("T-builder-live", identity["workspace_id"], "input")
    task.status, task.output, task.execution_mode = TaskStatus.QUEUED, None, TaskExecutionMode.CUSTOM
    task.assigned_agent_id = agent.id
    task.stages = [StageExecution(agent_id=agent.id, output_key="output")]
    pg_repo.save_custom_agent_task(task, expected_revision=1, **identity)
    asyncio.run(tasks._run_task(task.id, **identity))
    result = pg_repo.get_for_tenant(task.id, **identity)
    assert result.status == TaskStatus.COMPLETED and result.output == "Persistent provider output"
    assert result.custom_agent_revision == 1 and result.custom_agent_config_hash == agent.config_hash
    assert result.stages[0].total_tokens == 15
    provider.assert_awaited_once()
    with tenant_transaction(pg_repo.engine, **identity) as connection:
        assert connection.execute(select(dbm.agent_executions).where(dbm.agent_executions.c.simulation_id == task.id)).all()
    pg_repo.recycle_simulation(task.id, **identity)
    with pytest.raises(Exception, match="Execution evidence"):
        pg_repo.recycle_simulation(task.id, action="purge", confirmed=True, **identity)
    pg_repo.recycle_simulation(task.id, action="restore", **identity)
    assert pg_repo.get_for_tenant(task.id, **identity).model_dump(mode="json") == result.model_dump(mode="json")


def test_live_unicode_name_casefold_expansion_is_supported(pg_repo):
    identity = scope(pg_repo)
    definition = CustomAgentConfig(name="ﬃ" * 80, purpose="Review", instructions="Summarize")
    assert pg_repo.save_custom_agent(definition, **identity).config.name == definition.name
    with pytest.raises(AgentBuilderError) as duplicate:
        pg_repo.save_custom_agent(definition, **identity)
    assert duplicate.value.status_code == 409
