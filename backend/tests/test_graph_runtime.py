"""Real graph + existing task evidence integration, deterministic providers."""
import tempfile
import asyncio
from functools import wraps
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.api.routes import tasks
from app.agents.checkpointing import ContextSerializer, checkpoint_config
from app.agents.graph_runtime import execute_graph
from app.models.schemas import CreateTaskRequest, TaskStatus
from app.storage.database import Repository
from test_task_pipeline import FakeAgent
from test_tenant_repository_primitives import make_user


def async_test(function):
    @wraps(function)
    def run(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))
    return run


@pytest.fixture
def runtime_world():
    with tempfile.TemporaryDirectory() as directory:
        repo = Repository('sqlite:///'+str(Path(directory)/'runtime.db'))
        repo.initialize()
        repo.save_user(make_user('USR-test'))
        workspace = repo.ensure_personal_workspace('USR-test')
        order = []
        agents = {a: FakeAgent(a, order) for a in ('direct','research','data','analysis','summarizer','report')}
        with patch.object(tasks, 'repository', repo), patch('app.api.routes.messages.repository', repo), \
             patch('app.api.routes.simulation.repository', repo), \
             patch.object(tasks, '_IMPLEMENTED_AGENTS', agents), \
             patch.object(tasks.manager, 'broadcast', AsyncMock()) as broadcast:
            yield repo, agents, order, broadcast


def new_task(mode):
    return tasks.prepare_task(CreateTaskRequest(directive='Explain recruitment process',
        execution_mode=mode), workspace_id=tasks.repository.get_personal_workspace('USR-test')['id'])


@async_test
@pytest.mark.parametrize('mode', ['single','fixed','adaptive'])
async def test_graph_preserves_authoritative_lifecycle_handoffs_telemetry(runtime_world, mode):
    repo, agents, order, broadcast = runtime_world
    task = new_task(mode)
    repo.save(task)
    saver = InMemorySaver(serde=ContextSerializer())
    await tasks._run_task_inner(task.id, task=task, checkpointer=saver)
    stored = repo.get(task.id)
    assert stored.status == TaskStatus.COMPLETED
    assert order == [s.agent_id for s in stored.stages]
    assert all(s.status == 'completed' and s.output == s.agent_id+' actual output' for s in stored.stages)
    assert len(stored.messages) == len(stored.stages)-1
    assert stored.output == stored.stages[-1].output
    assert stored.provenance is not None and stored.evaluation is not None
    assert [e.type for e in stored.events].count('agent_completed') == len(stored.stages)
    assert [e.type for e in stored.events].count('simulation_completed') == 1
    assert all(c.kwargs['workspace_id'] == task.workspace_id for c in broadcast.await_args_list)
    snapshot = await saver.aget_tuple(checkpoint_config(task_id=task.id,workspace_id=task.workspace_id))
    assert snapshot.checkpoint['channel_values']['context'].prior_outputs[-1].text == stored.output


@async_test
@pytest.mark.parametrize('mode', ['single','fixed','adaptive'])
async def test_failure_reconnect_resume_does_not_repeat_completed_evidence(runtime_world, mode):
    repo, agents, order, broadcast = runtime_world
    task = new_task(mode)
    repo.save(task)
    failing = task.stages[-1].agent_id
    agents[failing].failure = 'provider unavailable'
    saver = InMemorySaver(serde=ContextSerializer())
    await tasks._run_task_inner(task.id, task=task, checkpointer=saver)
    failed = repo.get(task.id)
    assert failed.status == TaskStatus.FAILED and failed.output is None
    assert failed.stages[-1].status == 'failed' and failed.stages[-1].output is None
    previous_events = len([e for e in failed.events if e.type == 'agent_completed'])
    previous_messages = len(failed.messages)
    agents[failing].failure = None
    # Reload all application evidence, as a restarted worker does.
    await tasks._run_task_inner(task.id, task=failed, checkpointer=saver, resume=True)
    completed = repo.get(task.id)
    assert completed.status == TaskStatus.COMPLETED
    assert order == [s.agent_id for s in task.stages] + [failing]
    assert len(completed.messages) == len(completed.stages)-1
    assert len([e for e in completed.events if e.type == 'agent_completed']) == previous_events+1
    assert previous_messages <= len(completed.messages)


@async_test
async def test_evidence_ahead_of_checkpoint_replays_output_without_provider(runtime_world):
    repo, agents, order, _ = runtime_world
    task = new_task('fixed')
    repo.save(task)
    # Simulate a committed stage followed by process death before graph write.
    context = tasks._prepared_context(task)
    await tasks._run_stage(task, task.stages[0], context)
    result = await execute_graph(task)
    assert result == 'report actual output'
    assert order == ['research','data','analysis','summarizer','report']
    assert len(task.messages) == 4
    assert len([e for e in task.events if e.type == 'agent_completed']) == 5


@async_test
async def test_corrupt_checkpoint_denied_before_provider(runtime_world):
    repo, agents, order, _ = runtime_world
    task = new_task('single')
    saver = InMemorySaver(serde=ContextSerializer())
    config = checkpoint_config(task_id=task.id,workspace_id=task.workspace_id)
    from app.agents.graph_state import initial_graph_state
    from app.agents.graphs import build_single_graph
    state = initial_graph_state(task,tasks._prepared_context(task))
    state['workspace_id'] = 'OTHER'
    graph = build_single_graph(checkpointer=saver)
    await graph.aupdate_state(config,state)
    with pytest.raises(ValueError,match='binding mismatch'):
        await execute_graph(task,checkpointer=saver,config=config,resume=True)
    assert not order


@async_test
async def test_checkpoint_write_failure_fails_task_without_provider(runtime_world):
    repo, agents, order, _ = runtime_world
    task = new_task('single')
    repo.save(task)
    class BrokenSaver(InMemorySaver):
        async def aput(self, *args, **kwargs):
            raise RuntimeError('checkpoint storage failed')
    await tasks._run_task_inner(task.id,task=task,checkpointer=BrokenSaver())
    assert repo.get(task.id).status == TaskStatus.FAILED
    assert not order
    assert not task.messages and task.output is None

@async_test
async def test_metrics_use_existing_stage_sink_and_survive_retry(runtime_world):
    from app.agents.execution_context import current_execution
    repo, agents, order, _ = runtime_world
    task = new_task('single')
    repo.save(task)
    attempts = []
    class MeteredAgent:
        async def run(self, directive, context):
            stage = current_execution.get()
            stage.input_tokens, stage.output_tokens, stage.total_tokens = 3, 2, 5
            stage.model = 'deterministic'
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError('failure after metered response')
            return 'real answer'
    agents['direct'] = MeteredAgent()
    saver = InMemorySaver(serde=ContextSerializer())
    await tasks._run_task_inner(task.id,task=task,checkpointer=saver)
    failed = repo.get(task.id)
    previous_elapsed = failed.elapsed_seconds
    await tasks._run_task_inner(task.id,task=failed,checkpointer=saver,resume=True)
    stage = repo.get(task.id).stages[0]
    assert (stage.input_tokens,stage.output_tokens,stage.total_tokens) == (6,4,10)
    assert stage.model == 'deterministic'
    assert failed.elapsed_seconds >= previous_elapsed


@async_test
async def test_connection_failure_records_honest_terminal_state(runtime_world):
    from contextlib import asynccontextmanager
    repo, agents, order, _ = runtime_world
    task = new_task('single')
    repo.save(task)
    @asynccontextmanager
    async def unavailable(*args, **kwargs):
        raise RuntimeError('postgresql://secret:password@host/db')
        yield
    with patch.object(tasks.settings,'LANGGRAPH_RUNTIME_ENABLED',True), \
         patch.object(tasks.settings,'CHECKPOINT_DATABASE_URL','configured'), \
         patch.object(tasks,'postgres_checkpointer',unavailable):
        await tasks._run_task(task.id,task.workspace_id,'USR-test')
    stored = repo.get(task.id)
    assert stored.status == TaskStatus.FAILED and not order
    assert 'password' not in stored.error
    assert len([e for e in stored.events if e.type == 'simulation_failed']) == 1


@async_test
async def test_restart_marks_active_stage_failed_then_explicit_resume(runtime_world):
    repo, agents, order, _ = runtime_world
    task = new_task('fixed')
    repo.save(task)
    saver = InMemorySaver(serde=ContextSerializer())
    agents['data'].failure = 'interrupted'
    await tasks._run_task_inner(task.id,task=task,checkpointer=saver)
    interrupted = repo.get(task.id)
    interrupted.status = TaskStatus.IN_PROGRESS
    interrupted.stages[1].status = 'active'
    tasks._mark_interrupted_failed(interrupted)
    repo.save(interrupted)
    agents['data'].failure = None
    await tasks._run_task_inner(task.id,task=repo.get(task.id),checkpointer=saver,resume=True)
    assert order == ['research','data','data','analysis','summarizer','report']
    assert repo.get(task.id).status == TaskStatus.COMPLETED

@async_test
@pytest.mark.parametrize('mode',['single','fixed','adaptive'])
async def test_enabled_worker_dispatches_graph_through_existing_interface(runtime_world,mode):
    from contextlib import asynccontextmanager
    repo, agents, order, _ = runtime_world
    task = new_task(mode)
    repo.save_for_tenant(task,workspace_id=task.workspace_id,user_id='USR-test')
    saver = InMemorySaver(serde=ContextSerializer())
    @asynccontextmanager
    async def checkpoint_service(*args, **kwargs):
        assert kwargs['workspace_id'] == task.workspace_id
        assert kwargs['user_id'] == 'USR-test'
        yield saver
    with patch.object(tasks.settings,'LANGGRAPH_RUNTIME_ENABLED',True), \
         patch.object(tasks.settings,'CHECKPOINT_DATABASE_URL','configured'), \
         patch.object(tasks,'postgres_checkpointer',checkpoint_service), \
         patch.object(tasks,'_execute_mode',side_effect=AssertionError('legacy dispatcher called')):
        await tasks._run_task(task.id,task.workspace_id,'USR-test')
    assert repo.get_for_tenant(task.id,workspace_id=task.workspace_id,user_id='USR-test').status == TaskStatus.COMPLETED
    assert order == [s.agent_id for s in task.stages]


@async_test
async def test_worker_cannot_use_cache_to_bypass_workspace_visibility(runtime_world):
    from fastapi import HTTPException
    repo, agents, order, _ = runtime_world
    task = new_task('single')
    repo.save(task)
    tasks._TASKS[task.id] = task
    try:
        with pytest.raises(HTTPException):
            await tasks._run_task(task.id,'OTHER','USR-test')
        assert not order
    finally:
        tasks._TASKS.pop(task.id,None)
