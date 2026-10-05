from datetime import datetime, timezone

import pytest

from app.agents.execution_context import ExecutionContext, RouteSelection
from app.agents.graph_state import GraphRunState, initial_graph_state
from app.models.schemas import (
    RoutePlan,
    Task,
    TaskExecutionMode,
    TaskPriority,
    TaskStatus,
)


def task(mode=TaskExecutionMode.FIXED, route_plan=None):
    return Task(
        id="T-graph-state",
        directive="Analyze the supplied material.",
        assigned_agent_id="orchestrator",
        status=TaskStatus.QUEUED,
        priority=TaskPriority.MEDIUM,
        execution_mode=mode,
        started_at=datetime.now(timezone.utc),
        duration_seconds=0,
        progress_percent=0,
        workspace_id="WS-test",
        route_plan=route_plan,
    )


def adaptive_route():
    return RoutePlan(
        task_type="analysis",
        selected_agent_ids=("research", "analysis", "report"),
        skipped_agent_ids=("data", "summarizer"),
        required_capabilities=("research", "analysis", "report"),
        available_inputs=("original_directive",),
        reasons=("Deterministic test route.",),
        validation_status="valid",
    )


def test_initial_graph_state_keeps_execution_context_authoritative():
    run = task()
    context = ExecutionContext(
        original_directive=run.directive,
        execution_mode=run.execution_mode,
    )

    state: GraphRunState = initial_graph_state(
        run,
        context,
        user_id="USR-test",
    )

    assert state == {
        "task_id": "T-graph-state",
        "workspace_id": "WS-test",
        "user_id": "USR-test",
        "context": context,
        "current_agent": None,
        "completed_agents": (),
        "final_output": None,
    }

    assert "stages" not in state
    assert "events" not in state
    assert "messages" not in state
    assert "activities" not in state
    assert "provenance" not in state
    assert "evaluation" not in state
    assert "route_plan" not in state


def test_initial_graph_state_rejects_directive_mismatch():
    run = task()
    context = ExecutionContext(
        original_directive="Different directive",
        execution_mode=run.execution_mode,
    )

    with pytest.raises(ValueError, match="directive"):
        initial_graph_state(run, context)


def test_initial_graph_state_rejects_execution_mode_mismatch():
    run = task(TaskExecutionMode.FIXED)
    context = ExecutionContext(
        original_directive=run.directive,
        execution_mode=TaskExecutionMode.SINGLE,
    )

    with pytest.raises(ValueError, match="execution mode"):
        initial_graph_state(run, context)


def test_adaptive_graph_state_requires_route_parity():
    route = adaptive_route()
    run = task(TaskExecutionMode.ADAPTIVE, route)

    context = ExecutionContext(
        original_directive=run.directive,
        execution_mode=TaskExecutionMode.ADAPTIVE,
        route=RouteSelection(
            selected_agents=route.selected_agent_ids,
            skipped_agents=route.skipped_agent_ids,
        ),
    )

    state = initial_graph_state(run, context)

    assert state["context"].route.selected_agents == route.selected_agent_ids
    assert state["context"].route.skipped_agents == route.skipped_agent_ids


def test_adaptive_graph_state_rejects_missing_route():
    run = task(TaskExecutionMode.ADAPTIVE)

    context = ExecutionContext(
        original_directive=run.directive,
        execution_mode=TaskExecutionMode.ADAPTIVE,
    )

    with pytest.raises(ValueError, match="validated route"):
        initial_graph_state(run, context)


def test_adaptive_graph_state_rejects_route_mismatch():
    route = adaptive_route()
    run = task(TaskExecutionMode.ADAPTIVE, route)

    context = ExecutionContext(
        original_directive=run.directive,
        execution_mode=TaskExecutionMode.ADAPTIVE,
        route=RouteSelection(
            selected_agents=("research", "report"),
            skipped_agents=("data", "analysis", "summarizer"),
        ),
    )

    with pytest.raises(ValueError, match="selected agents"):
        initial_graph_state(run, context)
