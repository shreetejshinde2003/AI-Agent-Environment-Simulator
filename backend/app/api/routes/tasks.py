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
from app.api.routes.simulation import record_activity, register_task_created, register_task_finished
from app.models.schemas import CreateTaskRequest, Task, TaskPriority, TaskProgressStep, TaskStatus
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
        assigned_agent_id=payload.assigned_agent_id,
        status=TaskStatus.QUEUED,
        priority=payload.priority,
        started_at=datetime.now(timezone.utc),
        duration_seconds=0,
        progress_percent=0,
        progress_steps=[],
    )
    _TASKS[new_id] = task

    await manager.broadcast("task_created", task.model_dump(mode="json"))
    await register_task_created()
    await record_activity("orchestrator", f"assigned task {new_id} to {payload.assigned_agent_id}")

    background_tasks.add_task(_run_task, new_id)
    return task


async def _run_task(task_id: str) -> None:
    """
    The actual work: look up the assigned agent, run it, write the
    result (or error) back onto the task, broadcast every transition.
    Runs after the HTTP response for POST /tasks has already been sent.
    """
    task = _TASKS[task_id]
    agent = _IMPLEMENTED_AGENTS.get(task.assigned_agent_id)

    if agent is None:
        # Honest failure — the assigned agent isn't wired up yet. This
        # is the correct outcome for e.g. assigning to "web_search"
        # today: it should visibly fail, not hang forever "in progress".
        task.status = TaskStatus.FAILED
        task.error = (
            f"Agent '{task.assigned_agent_id}' is not implemented yet — "
            f"see backend/app/agents/{task.assigned_agent_id}_agent.py"
        )
        await manager.broadcast("task_updated", task.model_dump(mode="json"))
        await record_activity(task.assigned_agent_id, "task failed: agent not implemented yet")
        return

    task.status = TaskStatus.IN_PROGRESS
    task.progress_percent = 10
    task.progress_steps = [TaskProgressStep(label=f"{task.assigned_agent_id} is processing the directive", done=False)]
    await manager.broadcast("task_updated", task.model_dump(mode="json"))
    await record_activity(task.assigned_agent_id, "started processing the task")

    start = time.perf_counter()
    try:
        result_text = await agent.run(task.directive, context={})
        elapsed = time.perf_counter() - start

        task.status = TaskStatus.COMPLETED
        task.output = result_text
        task.duration_seconds = int(elapsed)
        task.progress_percent = 100
        task.progress_steps = [TaskProgressStep(label=f"{task.assigned_agent_id} completed the task", done=True)]

        await manager.broadcast("task_updated", task.model_dump(mode="json"))
        await record_activity(task.assigned_agent_id, "completed the task")
        await register_task_finished(response_time_seconds=elapsed, success=True)

    except Exception as exc:
        elapsed = time.perf_counter() - start
        task.status = TaskStatus.FAILED
        task.error = str(exc)
        task.duration_seconds = int(elapsed)

        await manager.broadcast("task_updated", task.model_dump(mode="json"))
        await record_activity(task.assigned_agent_id, f"task failed: {exc}")
        await register_task_finished(response_time_seconds=elapsed, success=False)
