"""Real FORCE RLS HR evidence and worker integration in random isolated schemas."""
import asyncio
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select, text
from app.agents import llm_client, hr_agents
from app.api.routes import hr_agents as routes
from app.models.schemas import HRAgentRequest, HRAgentEvidence, Task, TaskStatus, TaskPriority, StageExecution
from app.security.tenant_db_context import tenant_transaction
from app.storage import models as dbm
from app.security.rbac import AuthorizationError
from test_postgres_data_plane_integration import pg_repo
from test_hiring_postgres import setup, records
from test_hr_agents import response
from datetime import datetime, timezone
import uuid


def admitted(repo, identity, aid='hr_requirement_analysis'):
    req, knowledge, jd = records(repo, identity)
    request=HRAgentRequest(agent_id=aid, requirement={'id':req.id,'revision':1}, role_knowledge={'id':knowledge.id,'revision':1})
    sources=repo.bind_hr_sources(request, **identity)
    context, provenance=hr_agents.prepare(request,sources)
    evidence=HRAgentEvidence(request=request,implementation_version=hr_agents.VERSION,provider='groq',model=llm_client.DEFAULT_MODEL,
        sources=provenance,execution_context=context.model_dump(mode='json'),system_prompt=hr_agents.SYSTEM,
        output_schema=hr_agents.CATALOG[aid].output_model.model_json_schema(by_alias=True))
    task=Task(id='HRTEST-'+uuid.uuid4().hex,directive=context.original_directive,assigned_agent_id=aid,
        status=TaskStatus.QUEUED,priority=TaskPriority.MEDIUM,started_at=datetime.now(timezone.utc),duration_seconds=0,
        progress_percent=0,workspace_id=identity['workspace_id'],owner_id=identity['user_id'],task_type='hr_agent',
        hr_execution=evidence,stages=[StageExecution(agent_id=aid,output_key='hr_proposal')])
    repo.save_for_tenant(task, **identity)
    return task


def test_worker_persistence_rls_and_recycle_evidence(pg_repo, monkeypatch):
    owner, member=setup(pg_repo)
    task=admitted(pg_repo,owner)
    monkeypatch.setattr(routes,'repository',pg_repo)
    monkeypatch.setattr(llm_client,'call_llm',AsyncMock(return_value=response()))
    asyncio.run(routes.run_hr(task.id,**owner))
    saved=pg_repo.get_for_tenant(task.id,include_hr=True,**owner)
    assert saved.status==TaskStatus.COMPLETED
    assert saved.stages[0].total_tokens==50
    assert pg_repo.get_for_tenant(task.id,**owner) is None
    for table in (dbm.simulations,dbm.tasks,dbm.agent_executions,dbm.simulation_metrics,dbm.run_events):
        with pg_repo.engine.connect() as conn:
            assert conn.execute(select(table)).all()==[]
            flags=conn.execute(text('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=to_regclass(:name)'),{'name':table.name}).one()
            assert tuple(flags)==(True,True)
        with tenant_transaction(pg_repo.engine,**member) as conn:
            assert conn.execute(select(table)).all()
    pg_repo.deactivate_organization_human_role(workspace_id=owner['workspace_id'],target_user_id='USR-b',human_role='hr_recruiter',actor_user_id='USR-a')
    with tenant_transaction(pg_repo.engine,**member) as conn:
        for table in (dbm.simulations,dbm.tasks,dbm.agent_executions,dbm.simulation_metrics,dbm.run_events):
            assert conn.execute(select(table)).all()==[]
    pg_repo.recycle_simulation(task.id,**owner)
    assert pg_repo.list_recycled_simulations(**owner)[0]['id']==task.id
    pg_repo.recycle_simulation(task.id,action='restore',**owner)
    assert pg_repo.get_for_tenant(task.id,include_hr=True,**owner).stages==saved.stages
    pg_repo.initialize()
    assert pg_repo.get_for_tenant(task.id,include_hr=True,**owner).hr_execution==saved.hr_execution


@pytest.mark.parametrize('revoke',['role','membership'])
def test_worker_revocation_admission_and_during_provider(pg_repo, monkeypatch, revoke):
    owner,member=setup(pg_repo)
    task=admitted(pg_repo,member)
    monkeypatch.setattr(routes,'repository',pg_repo)
    def remove():
        if revoke=='role':
            pg_repo.deactivate_organization_human_role(workspace_id=owner['workspace_id'],target_user_id='USR-b',human_role='hr_recruiter',actor_user_id='USR-a')
        else:
            pg_repo.deactivate_organization_membership(workspace_id=owner['workspace_id'],target_user_id='USR-b',actor_user_id='USR-a')
    async def provider(**kwargs):
        remove()
        return response()
    monkeypatch.setattr(llm_client,'call_llm',AsyncMock(side_effect=provider))
    asyncio.run(routes.run_hr(task.id,**member))
    saved=pg_repo.get_for_tenant(task.id,include_hr=True,**owner)
    assert saved.status==TaskStatus.FAILED and saved.output is None
    assert saved.stages[0].total_tokens==50
    # Admission is durable even if caller revoked before the worker claims it.
    other=admitted(pg_repo,owner)
    pg_repo.deactivate_organization_human_role(workspace_id=owner['workspace_id'],target_user_id='USR-a',human_role='hr_recruiter',actor_user_id='USR-a')
    mock=AsyncMock()
    monkeypatch.setattr(llm_client,'call_llm',mock)
    asyncio.run(routes.run_hr(other.id,**owner))
    mock.assert_not_called()
    pg_repo.assign_organization_human_role(workspace_id=owner['workspace_id'],target_user_id='USR-a',human_role='hr_recruiter',actor_user_id='USR-a')
    assert pg_repo.get_for_tenant(other.id,include_hr=True,**owner).status==TaskStatus.FAILED


def test_cross_tenant_hr_evidence_and_claim(pg_repo):
    owner,member=setup(pg_repo)
    task=admitted(pg_repo,owner)
    other,_=pg_repo.create_organization(creator_user_id='USR-b',name='Foreign')
    outsider=dict(workspace_id=other['id'],user_id='USR-b')
    pg_repo.assign_organization_human_role(workspace_id=other['id'],target_user_id='USR-b',human_role='hr_recruiter',actor_user_id='USR-b')
    assert pg_repo.get_for_tenant(task.id,include_hr=True,**outsider) is None
    assert pg_repo.claim_hr_task(task.id,**outsider) is None
    assert pg_repo.list_hr_runs(**outsider)==[]
    with tenant_transaction(pg_repo.engine,**outsider) as conn:
        assert conn.execute(select(dbm.simulations)).all()==[]
