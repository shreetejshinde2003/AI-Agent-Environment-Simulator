"""Explicit custom-agent management path, separate from the system roster/routes."""
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.api.routes.workspaces import require_request_permission, request_user_id
from app.models.schemas import (CustomAgentConfig, CustomAgentDefinition, UpdateCustomAgentRequest,
                                CustomAgentRunRequest, Task)
from app.security.rbac import AuthorizationError, Permission
from app.storage.custom_agents import AgentBuilderError
from app.storage.database import repository
from app.core.config import settings

router = APIRouter(prefix="/agent-builder", tags=["agent-builder"])


def scope(request, workspace_id, permission):
    workspace = require_request_permission(request, workspace_id, permission)
    return dict(workspace_id=workspace["id"], user_id=request_user_id(request))


def operation(call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except AgentBuilderError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    except AuthorizationError as exc:
        raise HTTPException(403, {"code": "permission_denied", "message": "Permission denied."}) from exc


@router.get("/options")
async def options(request: Request, x_workspace_id: str | None = Header(default=None)):
    scope(request, x_workspace_id, Permission.AGENT_VIEW)
    return {"provider": "groq", "models": {"default": settings.GROQ_MODEL, "fast": settings.GROQ_FAST_MODEL},
            "inputContract": "text", "outputContract": "text", "capability": "text_generation"}


@router.get("", response_model=list[CustomAgentDefinition])
async def listing(request: Request, x_workspace_id: str | None = Header(default=None)):
    return operation(repository.list_custom_agents, **scope(request, x_workspace_id, Permission.AGENT_VIEW))


@router.post("", response_model=CustomAgentDefinition, status_code=201)
async def create(payload: CustomAgentConfig, request: Request, x_workspace_id: str | None = Header(default=None)):
    return operation(repository.save_custom_agent, payload, **scope(request, x_workspace_id, Permission.AGENT_MANAGE))


@router.get("/{agent_id}", response_model=CustomAgentDefinition)
async def detail(agent_id: str, request: Request, x_workspace_id: str | None = Header(default=None)):
    return operation(repository.get_custom_agent, agent_id, **scope(request, x_workspace_id, Permission.AGENT_VIEW))


@router.get("/{agent_id}/revisions", response_model=list[CustomAgentDefinition])
async def revisions(agent_id: str, request: Request, x_workspace_id: str | None = Header(default=None)):
    return operation(repository.custom_agent_revisions, agent_id, **scope(request, x_workspace_id, Permission.AGENT_VIEW))


@router.get("/{agent_id}/deletion-eligibility")
async def deletion_eligibility(agent_id: str, request: Request, x_workspace_id: str | None = Header(default=None)):
    identity = scope(request, x_workspace_id, Permission.AGENT_MANAGE)
    if agent_id in {"orchestrator", "research", "data", "analysis", "summarizer", "report", "direct", "web_search"}:
        raise HTTPException(409, {"code": "system_agent_protected", "message": "Built-in agents cannot be removed."})
    return operation(repository.custom_agent_deletion_eligibility, agent_id, **identity)


@router.put("/{agent_id}", response_model=CustomAgentDefinition)
async def update(agent_id: str, payload: UpdateCustomAgentRequest, request: Request,
                 x_workspace_id: str | None = Header(default=None)):
    config = CustomAgentConfig.model_validate(payload.model_dump(exclude={"expected_revision"}))
    return operation(repository.save_custom_agent, config, agent_id=agent_id, expected_revision=payload.expected_revision,
                     **scope(request, x_workspace_id, Permission.AGENT_MANAGE))


@router.post("/{agent_id}/runs", response_model=Task, status_code=202)
async def run(agent_id: str, payload: CustomAgentRunRequest, request: Request, background_tasks: BackgroundTasks,
              x_workspace_id: str | None = Header(default=None)):
    from app.api.routes import tasks
    from app.models.schemas import StageExecution, TaskExecutionMode, TaskPriority, TaskStatus
    import uuid
    identity = scope(request, x_workspace_id, Permission.AGENT_RUN)
    stamp = tasks.now()
    task_id = "T-" + uuid.uuid4().hex
    task = Task(id=task_id, simulation_id=task_id, directive=payload.text, assigned_agent_id=agent_id,
                execution_mode=TaskExecutionMode.CUSTOM, status=TaskStatus.QUEUED, priority=TaskPriority.MEDIUM,
                started_at=stamp, created_at=stamp, duration_seconds=0, progress_percent=0,
                workspace_id=identity["workspace_id"], stages=[StageExecution(agent_id=agent_id, output_key="output")])
    operation(repository.save_custom_agent_task, task, expected_revision=payload.expected_revision, **identity)
    await tasks.emit(task, "task_created", "Custom agent run queued", user_id=identity["user_id"])
    await tasks.register_task_created(task, user_id=identity["user_id"])
    background_tasks.add_task(tasks._run_task, task.id, identity["workspace_id"], identity["user_id"])
    return task
