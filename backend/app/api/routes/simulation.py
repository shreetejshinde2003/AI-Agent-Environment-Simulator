"""Legacy aggregate endpoints derived from persisted simulation records."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Header, Query, Request
from app.models.schemas import ActivityEvent, Task
from app.api.routes.agents import EXECUTABLE
from app.api.routes.workspaces import require_request_permission, request_user_id
from app.storage.database import repository
from app.security.rbac import Permission
from app.websocket.manager import manager

router = APIRouter(prefix="/simulation", tags=["simulation"])


def aggregate(runs=None):
    runs = repository.list() if runs is None else runs
    finished = [r for r in runs if r.status.value in ("completed", "failed")]
    completed = sum(r.status.value == "completed" for r in runs)
    stages = [s for r in runs for s in r.stages if s.started_at]
    latencies = [s.duration_seconds for s in stages if s.duration_seconds is not None]
    durations = [r.elapsed_seconds for r in finished if r.elapsed_seconds is not None]
    measured = [s for s in stages if s.total_tokens is not None]
    measured_runs = [r for r in finished if r.stages and
                     all(s.total_tokens is not None for s in r.stages if s.started_at)]
    return dict(
        simulationId=None, status="running" if any(r.status.value == "in_progress" for r in runs) else "stopped",
        startTime=None, durationSeconds=0, totalAgents=len(EXECUTABLE),
        activeAgents=len({s.agent_id for s in stages if s.status == "active"}),
        totalTasks=len(runs), completedTasks=completed, failedTasks=len(finished)-completed,
        totalMessages=sum(len(r.messages) for r in runs),
        avgResponseTimeSeconds=sum(durations)/len(durations) if durations else None,
        successRatePercent=round(completed/len(finished)*100, 1) if finished else None,
        totalAgentExecutions=len(stages), totalTokens=sum(s.total_tokens for s in measured),
        measuredExecutions=len(measured),
        avgAgentLatencySeconds=sum(latencies)/len(latencies) if latencies else None,
        avgTokensPerRun=(sum(sum(s.total_tokens or 0 for s in r.stages) for r in measured_runs)
                         / len(measured_runs)) if measured_runs else None,
    )


@router.get("/stats")
async def get_simulation_stats(
    request: Request,
    x_workspace_id: str | None = Header(default=None),
):
    workspace = require_request_permission(
        request, x_workspace_id, Permission.SIMULATION_VIEW
    )
    return aggregate(repository.list_for_tenant(
        workspace_id=workspace["id"], user_id=request_user_id(request)
    ))


@router.get("/activity", response_model=list[ActivityEvent])
async def get_activity_feed(
    request: Request,
    limit: int = Query(20, ge=1, le=1000),
    simulation_id: str | None = None,
    x_workspace_id: str | None = Header(default=None),
):
    workspace = require_request_permission(
        request, x_workspace_id, Permission.SIMULATION_VIEW
    )
    user_id = request_user_id(request)
    runs = (
        [repository.get_for_tenant(
            simulation_id, workspace_id=workspace["id"], user_id=user_id
        )]
        if simulation_id
        else repository.list_for_tenant(
            workspace_id=workspace["id"], user_id=user_id
        )
    )
    activity = [a for run in runs if run for a in run.activities]
    return sorted(activity, key=lambda a: a.timestamp)[-limit:]


async def record_activity(agent_id: str, text: str, *, task: Task, user_id: str | None = None):
    event = ActivityEvent(id=f"a-{uuid.uuid4().hex}", agent_id=agent_id, text=text,
                          timestamp=datetime.now(timezone.utc), simulation_id=task.id)
    task.activities.append(event)
    if user_id is not None and task.workspace_id is not None:
        repository.save_for_tenant(
            task, workspace_id=task.workspace_id, user_id=user_id
        )
    else:
        repository.save(task)
    await manager.broadcast(
        "activity_event",
        event.model_dump(mode="json"),
        workspace_id=task.workspace_id,
    )


async def register_task_created(task: Task, *, user_id: str | None = None):
    runs = (
        repository.list_for_tenant(
            workspace_id=task.workspace_id, user_id=user_id
        )
        if task.workspace_id and user_id
        else repository.list_for_workspace(task.workspace_id)
        if task.workspace_id
        else []
    )
    await manager.broadcast(
        "stats_updated",
        aggregate(runs),
        workspace_id=task.workspace_id,
    )


async def register_task_finished(
    task: Task, response_time_seconds: float, success: bool, *, user_id: str | None = None
):
    runs = (
        repository.list_for_tenant(
            workspace_id=task.workspace_id, user_id=user_id
        )
        if task.workspace_id and user_id
        else repository.list_for_workspace(task.workspace_id)
        if task.workspace_id
        else []
    )
    await manager.broadcast(
        "stats_updated",
        aggregate(runs),
        workspace_id=task.workspace_id,
    )


# Retain the legacy routes but explicitly describe their unsupported behavior.
@router.post("/pause")
@router.post("/resume")
@router.post("/stop")
async def unavailable_control(request: Request, x_workspace_id: str | None = Header(default=None)):
    workspace = require_request_permission(request, x_workspace_id, Permission.SIMULATION_VIEW)
    runs = repository.list_for_tenant(
        workspace_id=workspace["id"], user_id=request_user_id(request)
    )
    return {**aggregate(runs), "supported": False,
            "detail": "Execution controls are unavailable; active LLM calls run to completion."}
