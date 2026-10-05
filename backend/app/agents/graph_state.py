"""Canonical shared state for LangGraph execution.

The graph state is intentionally small.

ExecutionContext is the authoritative immutable carrier of validated agent
inputs and successful prior outputs.

Task and StageExecution remain authoritative for persistence, telemetry,
provenance, evaluation, messages, events, and lifecycle status.
"""

from typing import TypedDict

from app.agents.execution_context import AgentId, ExecutionContext
from app.models.schemas import Task, TaskExecutionMode


class GraphRunState(TypedDict):
    task_id: str
    workspace_id: str | None
    user_id: str | None
    context: ExecutionContext
    current_agent: AgentId | None
    completed_agents: tuple[AgentId, ...]
    final_output: str | None


def initial_graph_state(
    task: Task,
    context: ExecutionContext,
    *,
    user_id: str | None = None,
) -> GraphRunState:
    """Create graph state without duplicating persisted Task evidence."""

    if context.original_directive != task.directive:
        raise ValueError("Graph context directive does not match the task.")

    if context.execution_mode != task.execution_mode:
        raise ValueError("Graph context execution mode does not match the task.")

    if task.execution_mode == TaskExecutionMode.ADAPTIVE:
        if task.route_plan is None or context.route is None:
            raise ValueError("Adaptive graph execution requires a validated route.")

        if context.route.selected_agents != tuple(task.route_plan.selected_agent_ids):
            raise ValueError("Graph selected agents do not match the persisted route.")

        if context.route.skipped_agents != tuple(task.route_plan.skipped_agent_ids):
            raise ValueError("Graph skipped agents do not match the persisted route.")

    return GraphRunState(
        task_id=task.id,
        workspace_id=task.workspace_id,
        user_id=user_id,
        context=context,
        current_agent=None,
        completed_agents=(),
        final_output=None,
    )
