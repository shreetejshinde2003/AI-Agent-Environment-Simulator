"""Opt-in real saver persistence/reconnect acceptance using a restricted login.

No setup(), CREATE, DROP, production URL fallback, or broad cleanup. Deletes
only checkpoints for the two fresh, authorized test tasks. Application evidence
uses a temporary SQLite repository; production application-PG parity is a
separate activation gate.
"""
import os
import asyncio

import pytest
from psycopg.conninfo import conninfo_to_dict

from app.agents.checkpointing import postgres_checkpointer, checkpoint_config, CheckpointBusyError
from app.agents.graph_runtime import execute_graph
from app.api.routes import tasks
from app.models.schemas import TaskStatus
from app.security.rbac import AuthorizationError
from test_graph_runtime import runtime_world, new_task


@pytest.mark.parametrize('mode', ['single','fixed','adaptive'])
def test_real_checkpoint_reconnect_resume_and_tenant_denial(runtime_world, mode):
    url = os.environ.get('CHECKPOINT_TEST_DATABASE_URL')
    if not url:
        pytest.skip('CHECKPOINT_TEST_DATABASE_URL restricted local runtime login not configured')
    info = conninfo_to_dict(url)
    assert info.get('host') in {'127.0.0.1','localhost','::1'}
    assert info.get('dbname') == 'fm_tenant_test'
    assert not {'hostaddr','service','options'} & info.keys()
    repo, agents, order, _ = runtime_world
    task = new_task(mode)
    repo.save_for_tenant(task,workspace_id=task.workspace_id,user_id='USR-test')
    other = new_task(mode)
    repo.save_for_tenant(other,workspace_id=other.workspace_id,user_id='USR-test')
    config = checkpoint_config(task_id=task.id,workspace_id=task.workspace_id)
    identity = dict(repository=repo,task_id=task.id,workspace_id=task.workspace_id,user_id='USR-test')

    async def run():
        try:
            failing = task.stages[-1].agent_id
            agents[failing].failure = 'deterministic failure'
            async with postgres_checkpointer(url, **identity) as saver:
                with pytest.raises(CheckpointBusyError):
                    async with postgres_checkpointer(url, **identity):
                        pass
                async with saver.conn.cursor() as cur:
                    await cur.execute('SELECT current_database() AS name')
                    assert (await cur.fetchone())['name'] == 'fm_tenant_test'
                await tasks._run_task_inner(task.id,task=task,user_id='USR-test',checkpointer=saver)
                assert repo.get_for_tenant(task.id,workspace_id=task.workspace_id,user_id='USR-test').status == TaskStatus.FAILED
                foreign = checkpoint_config(task_id=other.id,workspace_id=other.workspace_id)
                with pytest.raises(AuthorizationError):
                    await saver.aget_tuple(foreign)
                with pytest.raises(AuthorizationError):
                    await saver.adelete_thread(foreign['configurable']['thread_id'])
                # Saver operations have not leaked a session setting.
                async with saver.conn.cursor() as cur:
                    await cur.execute("SELECT NULLIF(current_setting('app.checkpoint_thread_id',true),'') AS context")
                    assert (await cur.fetchone())['context'] is None
                    await cur.execute('SELECT thread_id FROM checkpoints')
                    assert await cur.fetchall() == []
            agents[failing].failure = None
            loaded = repo.get_for_tenant(task.id,workspace_id=task.workspace_id,user_id='USR-test')
            async with postgres_checkpointer(url, **identity) as saver:
                await tasks._run_task_inner(task.id,task=loaded,user_id='USR-test',checkpointer=saver,resume=True)
                assert loaded.status == TaskStatus.COMPLETED
                assert order == [s.agent_id for s in task.stages] + [failing]
            for change in ({'workspace_id':'OTHER'}, {'user_id':None}):
                with pytest.raises(AuthorizationError):
                    async with postgres_checkpointer(url, **{**identity, **change}):
                        pass
        finally:
            async with postgres_checkpointer(url, **identity) as saver:
                await saver.adelete_thread(config['configurable']['thread_id'])
    asyncio.run(run())
