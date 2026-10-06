"""LangGraph orchestration using the existing authoritative stage boundary."""
from app.agents.execution_context import ExecutionContext
from app.agents.graph_state import initial_graph_state
from app.agents.graphs import build_single_graph, build_fixed_graph, build_adaptive_graph
from app.agents.contracts import CONTRACTS
from app.agents.routing import validate_route
from app.models.schemas import TaskExecutionMode, MessageKind


GRAPH_MODES = (TaskExecutionMode.SINGLE, TaskExecutionMode.FIXED, TaskExecutionMode.ADAPTIVE)


def validated_sequence(task, context):
    if task.execution_mode == TaskExecutionMode.SINGLE:
        sequence = (('direct', 'final_answer'),)
    elif task.execution_mode == TaskExecutionMode.FIXED:
        sequence = tuple((aid, CONTRACTS[aid].output) for aid in
                         ('research', 'data', 'analysis', 'summarizer', 'report'))
    elif task.execution_mode == TaskExecutionMode.ADAPTIVE:
        if task.route_plan is None:
            raise ValueError('Adaptive route plan is missing')
        checked = validate_route(task.route_plan, context)
        if checked.validation_status != 'valid':
            raise ValueError(checked.validation_error)
        sequence = tuple((aid, CONTRACTS[aid].output) for aid in checked.selected_agent_ids)
    else:
        raise ValueError('Unsupported graph mode')
    if tuple((s.agent_id, s.output_key) for s in task.stages) != sequence:
        raise ValueError('Persisted stages do not match the execution route')
    seen_incomplete = False
    for stage in task.stages:
        if stage.status == 'completed':
            if seen_incomplete or not stage.output:
                raise ValueError('Completed stages must form an evidence-backed prefix')
        else:
            seen_incomplete = True
    return sequence


def validate_snapshot(task, values, base_context, sequence):
    """Reject state/evidence drift before executing or replaying any side effects."""
    if values.get('task_id') != task.id or values.get('workspace_id') != task.workspace_id:
        raise ValueError('Checkpoint task binding mismatch')
    completed = tuple(values.get('completed_agents', ()))
    selected = tuple(aid for aid, _ in sequence)
    if completed != selected[:len(completed)]:
        raise ValueError('Checkpoint route prefix mismatch')
    expected = base_context
    for index, aid in enumerate(completed):
        stage = task.stages[index]
        if stage.status != 'completed' or not stage.output:
            raise ValueError('Checkpoint success has no authoritative stage evidence')
        expected = expected.with_output(aid, stage.output)
    context = values.get('context')
    if not isinstance(context, ExecutionContext) or context != expected:
        raise ValueError('Checkpoint inputs or outputs differ from authoritative evidence')
    expected_output = task.stages[len(completed)-1].output if completed else None
    expected_agent = completed[-1] if completed else None
    if values.get('final_output') != expected_output or values.get('current_agent') != expected_agent:
        raise ValueError('Checkpoint cursor or final output differs from authoritative evidence')


async def execute_graph(task, *, user_id=None, checkpointer=None, config=None, resume=False):
    # Import at call time to preserve the task module's established patch seams.
    from app.api.routes import tasks
    context = tasks._prepared_context(task)
    sequence = validated_sequence(task, context)

    def node_for(index, agent_id):
        async def node(state):
            validate_snapshot(task, state, context, sequence)
            stage = task.stages[index]
            if tuple(state['completed_agents']) != tuple(aid for aid, _ in sequence[:index]):
                raise ValueError('Graph node is out of stage order')
            if stage.status == 'completed':
                # Evidence may have committed before the graph checkpoint did.
                result = stage.output
            else:
                result = await tasks._run_stage(task, stage, state['context'], user_id=user_id)
            next_context = state['context'].with_output(agent_id, result)
            if index < len(sequence) - 1:
                next_agent = sequence[index+1][0]
                matching = [m for m in task.messages if m.from_agent_id == agent_id
                            and m.to_agent_id == next_agent and m.output_key == stage.output_key]
                if matching and (len(matching) != 1 or matching[0].content != result):
                    raise ValueError('Persisted handoff differs from stage evidence')
                if not matching:
                    await tasks.record_message(agent_id, next_agent, MessageKind.RESPONSE, result,
                        task=task, output_key=stage.output_key, user_id=user_id)
                # Recover the event-only crash window without repeating the message.
                text = f'{agent_id} → {next_agent}: {stage.output_key}'
                if not any(e.type == 'message_created' and e.agent_id == agent_id and e.text == text for e in task.events):
                    await tasks.emit(task, 'message_created', text, agent_id, user_id)
            return {'context': next_context, 'current_agent': agent_id,
                    'completed_agents': (*state['completed_agents'], agent_id), 'final_output': result}
        return node

    nodes = {aid: node_for(index, aid) for index, (aid, _) in enumerate(sequence)}
    if task.execution_mode == TaskExecutionMode.SINGLE:
        graph = build_single_graph(node=nodes['direct'], checkpointer=checkpointer)
    else:
        builder = build_fixed_graph if task.execution_mode == TaskExecutionMode.FIXED else build_adaptive_graph
        graph = builder(**nodes, checkpointer=checkpointer)
    state = initial_graph_state(task, context, user_id=user_id)
    if checkpointer is not None:
        snapshot = await graph.aget_state(config)
        if snapshot.values:
            validate_snapshot(task, snapshot.values, context, sequence)
            if not resume:
                raise ValueError('Existing checkpoint requires explicit resume')
            state = None
        elif resume:
            raise ValueError('No durable checkpoint is available for resume')
    elif resume:
        raise ValueError('Resume requires durable checkpointing')
    options = {'durability': 'sync'} if checkpointer is not None else {}
    result = await graph.ainvoke(state, config=config, **options)
    validate_snapshot(task, result, context, sequence)
    if len(result['completed_agents']) != len(sequence):
        raise ValueError('Graph stopped before completing the selected route')
    return result['final_output']
