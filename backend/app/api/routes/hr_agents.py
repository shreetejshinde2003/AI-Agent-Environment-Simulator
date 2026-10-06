"""Authenticated HR assistance; Task and StageExecution own all evidence."""
import asyncio
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.agents import hr_agents
from app.agents.execution_context import ExecutionContext
from app.api.routes.hiring import operation, scope
from app.core.config import settings
from app.models.schemas import (HRAgentRequest, HRAgentEvidence, Task, TaskStatus,
                                TaskPriority, StageExecution, RunEvent)
from app.security.hr_roles import HRHumanPermission
from app.security.rbac import AuthorizationError
from app.security.tenant_db_context import tenant_transaction
from app.storage.database import repository

router = APIRouter(prefix="/hiring/agents", tags=["hr-agents"])


def now():
    return datetime.now(timezone.utc)


@router.get("")
def catalog(request: Request, x_workspace_id: str | None = Header(default=None)):
    identity = scope(request, x_workspace_id)
    with tenant_transaction(repository.engine, **identity) as connection:
        authorization = operation(repository._hiring_scope, connection, identity["workspace_id"],
                                  identity["user_id"], HRHumanPermission.HIRING_REQUEST_VIEW)
    return [{"id": aid, "title": contract.title, "purpose": contract.purpose,
             "version": hr_agents.VERSION, "provider": "groq", "model": hr_agents.llm_client.DEFAULT_MODEL,
             "canExecute": authorization.allows(HRHumanPermission.JD_REVIEW if contract.permission == "jd_review"
                                                  else HRHumanPermission.JD_DRAFT_EDIT),
             "outputSchema": contract.output_model.model_json_schema(by_alias=True), "proposalOnly": True}
            for aid, contract in hr_agents.CATALOG.items()]


@router.post("/runs", response_model=Task, status_code=202)
def admit(payload: HRAgentRequest, background_tasks: BackgroundTasks, request: Request,
          x_workspace_id: str | None = Header(default=None)):
    identity = scope(request, x_workspace_id)
    sources = operation(repository.bind_hr_sources, payload, **identity)
    context, provenance = operation(hr_agents.prepare, payload, sources)
    stamp = now()
    evidence = HRAgentEvidence(request=payload, implementation_version=hr_agents.VERSION, provider="groq",
        model=hr_agents.llm_client.DEFAULT_MODEL, sources=provenance,
        execution_context=context.model_dump(mode="json"), system_prompt=hr_agents.SYSTEM,
        output_schema=hr_agents.CATALOG[payload.agent_id].output_model.model_json_schema(by_alias=True))
    task = Task(id="HRRUN-" + uuid.uuid4().hex, directive=context.original_directive,
        assigned_agent_id=payload.agent_id, status=TaskStatus.QUEUED, priority=TaskPriority.MEDIUM,
        started_at=stamp, created_at=stamp, duration_seconds=0, progress_percent=0,
        owner_id=identity["user_id"], workspace_id=identity["workspace_id"], task_type="hr_agent",
        hr_execution=evidence, stages=[StageExecution(agent_id=payload.agent_id, output_key="hr_proposal")])
    operation(repository.save_for_tenant, task, **identity)
    background_tasks.add_task(run_hr, task.id, **identity)
    return task


@router.get("/runs", response_model=list[Task])
def history(request: Request, x_workspace_id: str | None = Header(default=None)):
    return operation(repository.list_hr_runs, **scope(request, x_workspace_id))


@router.get("/runs/{task_id}", response_model=Task)
def result(task_id: str, request: Request, x_workspace_id: str | None = Header(default=None)):
    identity = scope(request, x_workspace_id)
    task = operation(repository.get_for_tenant, task_id, include_hr=True, **identity)
    if task is None or task.hr_execution is None:
        raise HTTPException(404, "HR execution unavailable")
    return task


async def run_hr(task_id, *, workspace_id, user_id):
    task = repository.claim_hr_task(task_id, workspace_id=workspace_id, user_id=user_id)
    if task is None:
        return
    stage = task.stages[0]
    started = time.perf_counter()
    try:
        repository.bind_hr_sources(task.hr_execution.request, workspace_id=workspace_id, user_id=user_id)
        task.status = TaskStatus.IN_PROGRESS
        task.execution_started_at = now()
        stage.started_at = task.execution_started_at
        stage.status = "active"
        stage.model = task.hr_execution.model
        repository.save_for_tenant(task, workspace_id=workspace_id, user_id=user_id)
        context = ExecutionContext.model_validate(task.hr_execution.execution_context)
        # No tool dispatch: only the existing provider adapter is available.
        response = await asyncio.wait_for(hr_agents.execute(context, model=task.hr_execution.model,
            system_prompt=task.hr_execution.system_prompt, output_schema=task.hr_execution.output_schema), timeout=settings.HR_AGENT_TIMEOUT_SECONDS)
        stage.model = response.model
        stage.input_tokens, stage.output_tokens, stage.total_tokens = response.input_tokens, response.output_tokens, response.total_tokens
        output = hr_agents.validate_output(context, response.text)
        repository.bind_hr_sources(task.hr_execution.request, workspace_id=workspace_id, user_id=user_id)
        task.output = stage.output = output.model_dump_json(by_alias=True)
        task.status = TaskStatus.COMPLETED
        stage.status = "completed"
        task.progress_percent = 100
    except asyncio.CancelledError:
        task.status = TaskStatus.FAILED
        task.error = "HR execution interrupted. Create a new run to retry."
        raise
    except Exception as exc:
        task.status = TaskStatus.FAILED
        task.error = ("HR authorization changed; execution denied." if isinstance(exc, AuthorizationError) else
                      "HR provider request timed out. Create a new run to retry." if isinstance(exc, TimeoutError) else
                      "HR execution failed: provider unavailable or output contract invalid. Create a new run to retry.")
    finally:
        if task.status == TaskStatus.FAILED:
            stage.status = "failed"
            stage.error = task.error
            task.output = stage.output = None
        task.completed_at = stage.completed_at = now()
        task.elapsed_seconds = time.perf_counter() - started
        task.duration_seconds = int(task.elapsed_seconds)
        stage.duration_seconds = task.elapsed_seconds if stage.started_at else None
        task.events.append(RunEvent(id=uuid.uuid4().hex, type="hr_execution_" + task.status.value,
                                   timestamp=task.completed_at, agent_id=task.assigned_agent_id,
                                   text=task.error or "AI proposal completed; human review required."))
        repository.finalize_hr_task(task)
