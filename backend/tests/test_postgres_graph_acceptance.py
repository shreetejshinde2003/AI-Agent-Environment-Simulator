"""Local all-PostgreSQL acceptance with real worker-process death and resume.

Uses reviewed random-schema pg_repo cleanup and deletes only fresh task-bound
checkpoint threads. Providers are mocked at call_llm; actual agents, worker,
SQLAlchemy tenant/RLS transactions, and Psycopg saver execute normally.
"""
import asyncio
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import AsyncMock, patch

import pytest
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy import text

from app.agents.checkpointing import postgres_checkpointer, checkpoint_config
from app.agents.execution_context import ExecutionContext, AgentOutput
from app.api.routes import tasks
from app.models.schemas import CreateTaskRequest, TaskStatus
from app.security.rbac import AuthorizationError
from test_postgres_data_plane_integration import pg_repo


WORKER_SCRIPT = r'''
import asyncio
from contextlib import ExitStack
import json
import os
from unittest.mock import AsyncMock, patch
from sqlalchemy import create_engine
from app.api.routes import tasks, messages, simulation
from app.core.config import settings
from app.agents.llm_client import LLMResponse
from app.storage.database import Repository, normalize_url

repo = Repository(os.environ['TENANT_TEST_DATABASE_URL'])
repo._engine = create_engine(normalize_url(repo.url),pool_size=1,max_overflow=0,
    connect_args={'options': '-csearch_path='+os.environ['FM_ACCEPTANCE_SCHEMA']+',pg_catalog'})
repo._engine_url = repo.url

async def main():
    with ExitStack() as stack:
        for module in (tasks,messages,simulation):
            stack.enter_context(patch.object(module,'repository',repo))
        stack.enter_context(patch.object(tasks.manager,'broadcast',AsyncMock()))
        stack.enter_context(patch.object(settings,'LANGGRAPH_RUNTIME_ENABLED',True))
        stack.enter_context(patch.object(settings,'CHECKPOINT_DATABASE_URL',os.environ['CHECKPOINT_TEST_DATABASE_URL']))
        for aid in ('direct','research','data','analysis','summarizer','report'):
            async def provider(*args,_aid=aid,**kwargs):
                if os.environ['FM_ACCEPTANCE_ACTION']=='crash' and _aid==os.environ['FM_ACCEPTANCE_CRASH_AGENT']:
                    # Active-stage evidence has committed. Abrupt exit skips finally
                    # blocks and releases database connections via process teardown.
                    os._exit(73)
                return LLMResponse(text=_aid+' acceptance output',input_tokens=2,
                    output_tokens=3,response_time_seconds=0.001,model='deterministic')
            stack.enter_context(patch('app.agents.'+aid+'_agent.call_llm',AsyncMock(side_effect=provider)))
        await tasks._run_task(os.environ['FM_ACCEPTANCE_TASK'],os.environ['FM_ACCEPTANCE_WORKSPACE'],
            os.environ['FM_ACCEPTANCE_USER'],resume=os.environ['FM_ACCEPTANCE_ACTION']=='resume')
        task = repo.get_for_tenant(os.environ['FM_ACCEPTANCE_TASK'],
            workspace_id=os.environ['FM_ACCEPTANCE_WORKSPACE'],user_id=os.environ['FM_ACCEPTANCE_USER'])
        print(json.dumps({'status':task.status.value,'stage_count':len(task.stages)}))
    repo.engine.dispose()

asyncio.run(main())
'''


@pytest.fixture
def checkpoint_url():
    raw = os.environ.get('CHECKPOINT_TEST_DATABASE_URL')
    if not raw:
        pytest.skip('Restricted local CHECKPOINT_TEST_DATABASE_URL required')
    info = conninfo_to_dict(raw)
    assert info.get('host') in {'127.0.0.1','localhost','::1'}
    assert info.get('dbname') == 'fm_tenant_test'
    assert not {'hostaddr','service','options'} & info.keys()
    return raw


def new_task(repo, mode, workspace, user):
    task = tasks.prepare_task(CreateTaskRequest(directive='Explain recruitment process',execution_mode=mode),
                              workspace_id=workspace,user_id=user)
    repo.save_for_tenant(task,workspace_id=workspace,user_id=user)
    return task


def bound(repo, task, user):
    return dict(repository=repo,task_id=task.id,workspace_id=task.workspace_id,user_id=user)


@pytest.mark.parametrize('mode',['single','fixed','adaptive'])
def test_postgres_worker_death_recovery_resume_and_evidence_parity(pg_repo,checkpoint_url,mode):
    repo = pg_repo
    workspace = repo.get_personal_workspace('USR-a')['id']
    task = new_task(repo,mode,workspace,'USR-a')
    # A second task really belongs to a different Personal Workspace.
    foreign_workspace = repo.get_personal_workspace('USR-b')['id']
    foreign = new_task(repo,mode,foreign_workspace,'USR-b')
    with repo.engine.connect() as connection:
        schema = connection.execute(text('SELECT current_schema()')).scalar_one()
    crash_agent = task.stages[0 if mode=='single' else 1].agent_id
    env = {**os.environ,'PYTHONPATH':str(Path(__file__).parents[1]),
        'FM_ACCEPTANCE_SCHEMA':schema,'FM_ACCEPTANCE_TASK':task.id,
        'FM_ACCEPTANCE_WORKSPACE':workspace,'FM_ACCEPTANCE_USER':'USR-a',
        'FM_ACCEPTANCE_CRASH_AGENT':crash_agent}
    # The fixture keeps an admin connection plus one repository connection;
    # close the latter before the child connects to respect the two-slot login.
    repo.engine.dispose()

    async def inspect_and_cleanup(cleanup=False):
        async with postgres_checkpointer(checkpoint_url,**bound(repo,task,'USR-a')) as saver:
            config = checkpoint_config(task_id=task.id,workspace_id=workspace)
            if cleanup:
                await saver.adelete_thread(config['configurable']['thread_id'])
                return
            saved = await saver.aget_tuple(config)
            values = saved.checkpoint['channel_values']
            assert isinstance(values['context'],ExecutionContext)
            assert all(isinstance(value,AgentOutput) for value in values['context'].prior_outputs)
            assert tuple(values['completed_agents']) == tuple(s.agent_id for s in task.stages)
            assert values['final_output'] == task.stages[-1].agent_id+' acceptance output'
            # Both trusted scope checks and raw SQL with absent context fail closed.
            with pytest.raises(AuthorizationError):
                await saver.aget_tuple(checkpoint_config(task_id=foreign.id,workspace_id=foreign_workspace))
            with pytest.raises(RuntimeError,match='database operation failed'):
                async with saver._cursor() as cursor:
                    await cursor.execute('SELECT 1/0')
            assert await saver.aget_tuple(config) is not None
            async with saver.conn.cursor() as cursor:
                await cursor.execute("SELECT NULLIF(current_setting('app.checkpoint_thread_id',true),'') AS scope")
                assert (await cursor.fetchone())['scope'] is None
                await cursor.execute('SELECT thread_id FROM checkpoints')
                assert await cursor.fetchall() == []
        for changed in ({'user_id':None},{'workspace_id':foreign_workspace},{'user_id':'USR-b'}):
            with pytest.raises(AuthorizationError):
                async with postgres_checkpointer(checkpoint_url,**{**bound(repo,task,'USR-a'),**changed}):
                    pass

    try:
        crashed = subprocess.run([sys.executable,'-'],input=WORKER_SCRIPT,text=True,capture_output=True,
            env={**env,'FM_ACCEPTANCE_ACTION':'crash'},timeout=30)
        assert crashed.returncode == 73, crashed.stderr
        interrupted = repo.get_for_tenant(task.id,workspace_id=workspace,user_id='USR-a')
        assert interrupted.status == TaskStatus.IN_PROGRESS
        assert next(s for s in interrupted.stages if s.agent_id==crash_agent).status == 'active'
        completed_before = [s.agent_id for s in interrupted.stages if s.status=='completed']
        original_messages = [m.id for m in interrupted.messages]
        assert repo.recover_interrupted_tasks(tasks._mark_interrupted_failed) == 2  # Includes foreign queued task.
        assert repo.recover_interrupted_tasks(tasks._mark_interrupted_failed) == 0
        failed = repo.get_for_tenant(task.id,workspace_id=workspace,user_id='USR-a')
        assert failed.status == TaskStatus.FAILED and failed.output is None
        repo.engine.dispose()
        resumed = subprocess.run([sys.executable,'-'],input=WORKER_SCRIPT,text=True,capture_output=True,
            env={**env,'FM_ACCEPTANCE_ACTION':'resume'},timeout=30)
        assert resumed.returncode == 0, resumed.stderr
        completed = repo.get_for_tenant(task.id,workspace_id=workspace,user_id='USR-a')
        assert completed.status == TaskStatus.COMPLETED
        assert completed.provenance == task.provenance and completed.route_plan == task.route_plan
        assert completed.evaluation is not None
        assert len(completed.stages) == len(task.stages)
        assert all(s.status=='completed' and s.total_tokens==5 and s.model=='deterministic' for s in completed.stages)
        assert len(completed.messages) == len(task.stages)-1
        assert [m.id for m in completed.messages[:len(original_messages)]] == original_messages
        assert completed.output == completed.stages[-1].output
        for aid in completed_before:
            assert sum(e.type=='agent_started' and e.agent_id==aid for e in completed.events) == 1
        assert sum(e.type=='agent_completed' for e in completed.events) == len(task.stages)
        assert sum(e.type=='simulation_completed' for e in completed.events) == 1
        assert repo.get_for_tenant(task.id,workspace_id=foreign_workspace,user_id='USR-b') is None
        asyncio.run(inspect_and_cleanup())
    finally:
        asyncio.run(inspect_and_cleanup(cleanup=True))


def test_checkpoint_membership_revocation_reauthorizes_live_connection(pg_repo,checkpoint_url):
    repo = pg_repo
    organization,code = repo.create_organization(creator_user_id='USR-b',name='Checkpoint acceptance')
    repo.join_organization(user_id='USR-a',join_code=code)
    task = new_task(repo,'single',organization['id'],'USR-a')

    async def run():
        try:
            async with postgres_checkpointer(checkpoint_url,**bound(repo,task,'USR-a')) as saver:
                config = checkpoint_config(task_id=task.id,workspace_id=task.workspace_id)
                assert await saver.aget_tuple(config) is None
                repo.deactivate_organization_membership(workspace_id=organization['id'],
                    actor_user_id='USR-b',target_user_id='USR-a')
                with pytest.raises(AuthorizationError):
                    await saver.aget_tuple(config)
                with pytest.raises(AuthorizationError):
                    await saver.aput_writes(config,[],'node')
                with pytest.raises(AuthorizationError):
                    await saver.adelete_thread(config['configurable']['thread_id'])
        finally:
            async with postgres_checkpointer(checkpoint_url,**bound(repo,task,'USR-b')) as owner:
                await owner.adelete_thread(checkpoint_config(task_id=task.id,workspace_id=task.workspace_id)['configurable']['thread_id'])
    asyncio.run(run())
