"""
app/api/routes/tasks.py

Endpoints for the Task Summary page and the "Task Details" panel on the
live dashboard. Backed by in-memory mock data for now — see the same
note in routes/agents.py about swapping this for storage later.
"""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.models.schemas import CreateTaskRequest, Task, TaskPriority, TaskProgressStep, TaskStatus
from app.websocket.manager import manager
from app.agents.research_agent import ResearchAgent

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ----------------------------------------------------------------------
# TEMPORARY in-memory mock data — replace with DB query once storage
# is activated (app/storage/database.py checklist).
# ----------------------------------------------------------------------
_MOCK_TASKS: dict[str, Task] = {
    "T-1024": Task(
        id="T-1024",
        directive="Search for top competitors in the AI market and collect key information like product, pricing, and recent news.",
        assigned_agent_id="web_search",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        started_at=datetime.now(timezone.utc),
        duration_seconds=150,
        progress_percent=65,
        progress_steps=[
            TaskProgressStep(label="Identified 12 competitor websites", done=True),
            TaskProgressStep(label="Extracted basic company information", done=True),
            TaskProgressStep(label="Collecting pricing and product details", done=False),
            TaskProgressStep(label="Compiling results", done=False),
        ],
    ),
}


@router.get("", response_model=list[Task])
async def list_tasks():
    """GET /api/v1/tasks — powers the Task Summary page."""
    return list(_MOCK_TASKS.values())


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str):
    """GET /api/v1/tasks/{id} — powers the Task Details panel."""
    task = _MOCK_TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task


@router.post("", response_model=Task, status_code=201)
async def create_task(payload: CreateTaskRequest):

    new_id = f"T-{1000 + len(_MOCK_TASKS) + 1}"

    task = Task(
        id=new_id,
        directive=payload.directive,
        assigned_agent_id=payload.assigned_agent_id,
        status=TaskStatus.IN_PROGRESS,
        priority=payload.priority,
        started_at=datetime.now(timezone.utc),
        duration_seconds=0,
        progress_percent=10,
        progress_steps=[
            TaskProgressStep(label="Task created", done=True),
            TaskProgressStep(label="Research Agent running", done=False),
        ],
    )

    _MOCK_TASKS[new_id] = task

    await manager.broadcast(
        "task_created",
        task.model_dump(mode="json")
    )

    # ------------------------------
    # Execute the Research Agent
    # ------------------------------
    agent = ResearchAgent()
    start = time.perf_counter()

    result = await agent.run(
        directive=payload.directive,
        context={}
    )
    elapsed = time.perf_counter() - start
    # ------------------------------
    # Update task after completion
    # ------------------------------
    task.status = TaskStatus.COMPLETED
    task.progress_percent = 100
    task.duration_seconds = round(elapsed)

    task.progress_steps = [
        TaskProgressStep(label="Task created", done=True),
        TaskProgressStep(label="Research completed", done=True),
    ]

    # Temporary: print the result in the backend terminal
    print("\n==============================")
    print("Research Agent Output")
    print("==============================")
    print(result)
    print("==============================\n")

    await manager.broadcast(
        "task_completed",
        task.model_dump(mode="json")
    )

    return task
