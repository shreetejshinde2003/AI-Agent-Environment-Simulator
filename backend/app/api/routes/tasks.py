"""
app/api/routes/tasks.py

Endpoints for the Task Summary page and the "Task Details" panel on the
live dashboard.

THIS is the file that actually closes the loop between "agent output
appears in the terminal" and "agent output appears on the dashboard".
# Creating a task invokes the assigned implemented agent in the background.
# Currently implemented: research, data, analysis, summarizer, report.
# The result (or error) is written back onto the Task and broadcast over WebSocket.
# """

import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.agents.research_agent import ResearchAgent
from app.api.routes.messages import record_message
from app.api.routes.simulation import record_activity, register_task_created, register_task_finished
from app.models.schemas import (
    CreateTaskRequest,
    MessageKind,
    Task,
    TaskExecutionMode,
    TaskPriority,
    TaskProgressStep,
    TaskStatus,
)
from app.websocket.manager import manager


from app.agents.data_agent import DataAgent
from app.agents.analysis_agent import AnalysisAgent
from app.agents.summarizer_agent import SummarizerAgent
from app.agents.report_agent import ReportAgent

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ----------------------------------------------------------------------
# TEMPORARY in-memory task store — replace with a DB query once storage
# is activated (app/storage/database.py checklist). Starts empty (not
# a fake pre-populated "T-1024") so what you see is only what you've
# actually created.
# ----------------------------------------------------------------------
_TASKS: dict[str, Task] = {}

# ----------------------------------------------------------------------
# Which agents actually work right now. One shared instance per agent
# (not a new one per task) so stats_tracker accumulates real
# calls_made/avg_response_time across every task that agent handles —
# matches how app/agents/orchestrator.py's reserved example reuses one
# instance per agent across a whole graph run.


# Which agents actually work right now. One shared instance per agent
# so stats_tracker accumulates real calls_made/avg_response_time across
# every task that agent handles.
# Add an entry here when another agent becomes executable.
# ----------------------------------------------------------------------
_IMPLEMENTED_AGENTS = {
    "research": ResearchAgent(),
    "data": DataAgent(),
    # "web_search": WebSearchAgent(),
    "analysis": AnalysisAgent(),
    "summarizer": SummarizerAgent(),
    "report": ReportAgent(),
}

# The full workflow deliberately lives beside the existing task executor.
# It uses the same agent instances, task store, activity log, messages, and
# WebSocket broadcasts as a single-agent task; LangGraph is not involved.
# Each tuple names the agent and the context field its real output provides
# to the following stage.
_PIPELINE_STAGES = (
    ("research", "research_findings"),
    ("data", "structured_data"),
    ("analysis", "insights"),
    ("summarizer", "summary"),
    ("report", "final_report"),
)


@router.get("", response_model=list[Task])
async def list_tasks():
    """GET /api/v1/tasks — powers the Task Summary page."""
    return list(_TASKS.values())


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str):
    """GET /api/v1/tasks/{id} — powers the Task Details panel."""
    task = _TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task


@router.post("", response_model=Task, status_code=201)
async def create_task(payload: CreateTaskRequest, background_tasks: BackgroundTasks):
    """
    POST /api/v1/tasks — powers the 'Create Task' quick action.

    Creates the task in QUEUED state, returns immediately (so the
    frontend isn't blocked waiting for an LLM call that might take a
    while), then runs the actual agent in the background. Every state
    change — queued -> in_progress -> completed/failed — is written
    back onto the Task and broadcast, so the dashboard updates live
    without polling.
    """
    new_id = f"T-{uuid.uuid4().hex[:8]}"  # USER-DEFINED: swap for a DB auto-increment once storage is activated

    task = Task(
        id=new_id,
        directive=payload.directive,
        assigned_agent_id=(
            "orchestrator"
            if payload.execution_mode == TaskExecutionMode.FULL_PIPELINE
            else payload.assigned_agent_id
        ),
        status=TaskStatus.QUEUED,
        priority=payload.priority,
        execution_mode=payload.execution_mode,
        started_at=datetime.now(timezone.utc),
        duration_seconds=0,
        progress_percent=0,
        progress_steps=[],
    )
    _TASKS[new_id] = task

    await manager.broadcast("task_created", task.model_dump(mode="json"))
    await register_task_created()
    activity_target = (
        "the full multi-agent pipeline"
        if task.execution_mode == TaskExecutionMode.FULL_PIPELINE
        else task.assigned_agent_id
    )
    await record_activity("orchestrator", f"assigned task {new_id} to {activity_target}")

    background_tasks.add_task(_run_task, new_id)
    return task


async def _run_pipeline(task: Task) -> str:
    """Run the supported agents in order, carrying real outputs forward."""
    context: dict[str, str] = {}
    task.progress_steps = [
        TaskProgressStep(label=f"{agent_id} is waiting", done=False)
        for agent_id, _ in _PIPELINE_STAGES
    ]

    for index, (agent_id, output_key) in enumerate(_PIPELINE_STAGES):
        agent = _IMPLEMENTED_AGENTS[agent_id]
        task.progress_percent = 10 + int(index * 80 / len(_PIPELINE_STAGES))
        task.progress_steps[index] = TaskProgressStep(
            label=f"{agent_id} is processing the directive",
            done=False,
        )
        await manager.broadcast("task_updated", task.model_dump(mode="json"))
        await record_activity(agent_id, "started pipeline stage")

        try:
            result_text = await agent.run(task.directive, context=context)
        except Exception as exc:
            await record_activity(agent_id, f"pipeline stage failed: {exc}")
            raise

        context[output_key] = result_text
        task.progress_percent = 10 + int((index + 1) * 80 / len(_PIPELINE_STAGES))
        task.progress_steps[index] = TaskProgressStep(
            label=f"{agent_id} completed the task",
            done=True,
        )

        if index < len(_PIPELINE_STAGES) - 1:
            next_agent_id = _PIPELINE_STAGES[index + 1][0]
            await record_message(
                agent_id,
                next_agent_id,
                MessageKind.RESPONSE,
                result_text,
            )
            await record_activity(agent_id, f"handed off output to {next_agent_id}")

        await manager.broadcast("task_updated", task.model_dump(mode="json"))

    return context["final_report"]


async def _run_task(task_id: str) -> None:
    """
    The actual work: look up the assigned agent, run it, write the
    result (or error) back onto the task, broadcast every transition.
    Runs after the HTTP response for POST /tasks has already been sent.
    """
    task = _TASKS[task_id]
    start = time.perf_counter()

    if task.execution_mode == TaskExecutionMode.SINGLE_AGENT:
        agent = _IMPLEMENTED_AGENTS.get(task.assigned_agent_id)
        if agent is None:
            # Honest failure — Web Search and the orchestrator are not direct
            # executable agents. The pipeline has its own execution mode.
            elapsed = time.perf_counter() - start
            task.status = TaskStatus.FAILED
            task.error = (
                f"Agent '{task.assigned_agent_id}' is not implemented yet — "
                f"see backend/app/agents/{task.assigned_agent_id}_agent.py"
            )
            task.duration_seconds = int(elapsed)
            await manager.broadcast("task_updated", task.model_dump(mode="json"))
            await record_activity(task.assigned_agent_id, "task failed: agent not implemented yet")
            await register_task_finished(response_time_seconds=elapsed, success=False)
            return

    task.status = TaskStatus.IN_PROGRESS
    task.progress_percent = 10
    if task.execution_mode == TaskExecutionMode.FULL_PIPELINE:
        task.progress_steps = [
            TaskProgressStep(label=f"{agent_id} is waiting", done=False)
            for agent_id, _ in _PIPELINE_STAGES
        ]
    else:
        task.progress_steps = [TaskProgressStep(label=f"{task.assigned_agent_id} is processing the directive", done=False)]
    await manager.broadcast("task_updated", task.model_dump(mode="json"))
    if task.execution_mode == TaskExecutionMode.FULL_PIPELINE:
        await record_activity("orchestrator", "started the full multi-agent pipeline")
    else:
        await record_activity(task.assigned_agent_id, "started processing the task")

    try:
        if task.execution_mode == TaskExecutionMode.FULL_PIPELINE:
            result_text = await _run_pipeline(task)
        else:
            result_text = await agent.run(task.directive, context={})
        elapsed = time.perf_counter() - start

        task.status = TaskStatus.COMPLETED
        task.output = result_text
        task.duration_seconds = int(elapsed)
        task.progress_percent = 100
        if task.execution_mode == TaskExecutionMode.SINGLE_AGENT:
            task.progress_steps = [TaskProgressStep(label=f"{task.assigned_agent_id} completed the task", done=True)]

        await manager.broadcast("task_updated", task.model_dump(mode="json"))
        if task.execution_mode == TaskExecutionMode.FULL_PIPELINE:
            await record_activity("orchestrator", "completed the full multi-agent pipeline")
        else:
            await record_activity(task.assigned_agent_id, "completed the task")
        await register_task_finished(response_time_seconds=elapsed, success=True)

    except Exception as exc:
        elapsed = time.perf_counter() - start
        task.status = TaskStatus.FAILED
        task.error = str(exc)
        task.duration_seconds = int(elapsed)

        await manager.broadcast("task_updated", task.model_dump(mode="json"))
        if task.execution_mode == TaskExecutionMode.FULL_PIPELINE:
            await record_activity("orchestrator", f"pipeline failed: {exc}")
        else:
            await record_activity(task.assigned_agent_id, f"task failed: {exc}")
        await register_task_finished(response_time_seconds=elapsed, success=False)
