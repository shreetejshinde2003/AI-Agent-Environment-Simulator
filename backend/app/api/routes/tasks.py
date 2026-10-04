"""Compatible task API and the V1 sequential five-agent execution engine."""
import asyncio
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from pydantic import ValidationError
from app.experiments.evaluation import (
    build_run_evaluation,
    evaluate_quality_judgment,
)
from app.agents.research_agent import ResearchAgent
from app.agents.data_agent import DataAgent
from app.agents.analysis_agent import AnalysisAgent
from app.agents.summarizer_agent import SummarizerAgent
from app.agents.report_agent import ReportAgent
from app.agents.direct_agent import DirectAgent
from app.agents.execution_context import AgentInputError, ExecutionContext, RouteSelection, current_execution
from app.agents.contracts import CONTRACTS
from app.agents.routing import inline_source, plan_route, validate_route
from app.api.routes.messages import record_message
from app.api.routes.simulation import record_activity, register_task_created, register_task_finished
from app.api.routes.workspaces import require_request_permission
from app.core.errors import safe_error
from app.datasets.registry import context_for_dataset
from app.models.schemas import (
    CreateTaskRequest, MessageKind, Task, TaskExecutionMode,
    TaskProgressStep, TaskStatus, StageExecution, RunEvent,
    RunEvaluation,
)
from app.storage.database import repository
from app.security.rbac import Permission
from app.websocket.manager import manager
from app.agents.llm_client import DEFAULT_MODEL, DEFAULT_MAX_TOKENS
from app.experiments.provenance import build_run_provenance

router = APIRouter(prefix="/tasks", tags=["tasks"])
_TASKS: dict[str, Task] = {}  # Active process cache; SQLite is authoritative for reads.
_IMPLEMENTED_AGENTS = {
    "research": ResearchAgent(), "data": DataAgent(), "analysis": AnalysisAgent(),
    "summarizer": SummarizerAgent(), "report": ReportAgent(), "direct": DirectAgent(),
}
_PIPELINE_STAGES = (
    ("research", "research_findings"), ("data", "structured_data"),
    ("analysis", "insights"), ("summarizer", "summary"), ("report", "final_report"),
)


def now():
    return datetime.now(timezone.utc)


async def emit(task: Task, event_type: str, text: str, agent_id: str | None = None):
    """Commit authoritative state before notifying clients."""
    event = RunEvent(id=uuid.uuid4().hex, type=event_type, text=text,
                     agent_id=agent_id, timestamp=now())
    task.events.append(event)
    repository.save(task)
    await manager.broadcast(
        event_type,
        {"simulationId": task.id,
         "executionMode": task.execution_mode.value,
         **event.model_dump(mode="json")},
        workspace_id=task.workspace_id,
    )
    await manager.broadcast(
        "task_updated",
        task.model_dump(mode="json"),
        workspace_id=task.workspace_id,
    )


def get_record(task_id: str, workspace_id: str | None = None) -> Task:
    task = (
        repository.get_for_workspace(task_id, workspace_id)
        if workspace_id is not None
        else repository.get(task_id)
    )
    if task is None:
        raise HTTPException(404, "Simulation not found")
    return task


@router.get("", response_model=list[Task])
async def list_tasks(
    request: Request,
    x_workspace_id: str | None = Header(default=None),
):
    workspace = require_request_permission(
        request, x_workspace_id, Permission.SIMULATION_VIEW
    )
    return repository.list_for_workspace(workspace["id"])


@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: str,
    request: Request,
    x_workspace_id: str | None = Header(default=None),
):
    workspace = require_request_permission(
        request, x_workspace_id, Permission.SIMULATION_VIEW
    )
    return get_record(task_id, workspace["id"])


@router.post("/{task_id}/evaluate", response_model=RunEvaluation)
async def evaluate_task_quality(
    task_id: str,
    request: Request,
    x_workspace_id: str | None = Header(default=None),
):
    """Explicitly run the blinded quality judge for one completed research run."""

    workspace = require_request_permission(
        request, x_workspace_id, Permission.SIMULATION_EVALUATE
    )
    task = get_record(task_id, workspace["id"])

    if task.execution_mode not in (
        TaskExecutionMode.SINGLE,
        TaskExecutionMode.FIXED,
        TaskExecutionMode.ADAPTIVE,
    ):
        raise HTTPException(
            422,
            detail={
                "code": "evaluation_not_supported",
                "message": (
                    "Quality evaluation is available only for "
                    "Single, Fixed and Adaptive research runs."
                ),
            },
        )

    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(
            409,
            detail={
                "code": "task_not_completed",
                "message": (
                    "Quality evaluation requires a completed research run."
                ),
            },
        )

    # Idempotency: never spend another evaluator request when a
    # quality judgment is already persisted.
    if (
        task.evaluation is not None
        and task.evaluation.quality is not None
    ):
        return task.evaluation

    # Historical completed research runs may predate objective
    # evaluation persistence. Reconstruct objective evidence from
    # their stored task telemetry without an LLM call.
    base_evaluation = (
        task.evaluation
        if task.evaluation is not None
        else build_run_evaluation(task)
    )

    try:
        quality = await evaluate_quality_judgment(task)

    except ValueError as exc:
        raise HTTPException(
            502,
            detail={
                "code": "invalid_evaluator_response",
                "message": str(exc),
            },
        ) from exc

    except Exception as exc:
        raise HTTPException(
            502,
            detail={
                "code": "evaluation_provider_error",
                "message": safe_error(exc),
            },
        ) from exc

    task.evaluation = RunEvaluation(
        task_id=base_evaluation.task_id,
        experiment_id=base_evaluation.experiment_id,
        input_fingerprint=base_evaluation.input_fingerprint,
        evaluated_at=now(),
        objective=base_evaluation.objective,
        quality=quality,
    )

    repository.save(task)

    await manager.broadcast(
        "evaluation_completed",
        {
            "simulationId": task.id,
            "evaluation": task.evaluation.model_dump(mode="json"),
        },
        workspace_id=task.workspace_id,
    )

    await manager.broadcast(
        "task_updated",
        task.model_dump(mode="json"),
        workspace_id=task.workspace_id,
    )

    return task.evaluation


def prepare_task(
    payload: CreateTaskRequest,
    *,
    experiment_id: str | None = None,
    workspace_id: str | None = None,
) -> Task:
    if not payload.directive.strip():
        raise HTTPException(422, "Directive must not be blank")

    if (
        payload.execution_mode == TaskExecutionMode.SINGLE_AGENT
        and not payload.assigned_agent_id
    ):
        raise HTTPException(
            422,
            "Individual specialist execution requires assignedAgentId",
        )

    uploads = []
    for upload_id in dict.fromkeys(payload.upload_ids):
        upload = repository.get_upload(upload_id)
        if upload is None:
            raise HTTPException(404, "Uploaded context not found")
        uploads.append(upload)

    benchmark_context = None
    dataset_checksum = None

    if payload.dataset_id:
        dataset = repository.get_dataset(payload.dataset_id)
        if dataset is None:
            raise HTTPException(404, "Benchmark dataset not registered")

        try:
            benchmark_context = context_for_dataset(dataset)
        except (OSError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

        dataset_checksum = dataset["checksum"]

    requested_task_type = payload.task_type
    task_id = f"T-{uuid.uuid4().hex[:12]}"

    is_pipeline = payload.execution_mode == TaskExecutionMode.FIXED
    is_single = payload.execution_mode == TaskExecutionMode.SINGLE
    is_adaptive = payload.execution_mode == TaskExecutionMode.ADAPTIVE

    sequence = _PIPELINE_STAGES if is_pipeline else (
        ("direct", "final_answer")
        if is_single
        else (payload.assigned_agent_id, "output"),
    )

    task = Task(
        id=task_id,
        simulation_id=task_id,
        directive=payload.directive.strip(),
        title=payload.title,
        assigned_agent_id=(
            "orchestrator"
            if is_pipeline or is_adaptive
            else "direct"
            if is_single
            else payload.assigned_agent_id
        ),
        execution_mode=payload.execution_mode,
        priority=payload.priority,
        status=TaskStatus.QUEUED,
        started_at=now(),
        created_at=now(),
        duration_seconds=0,
        progress_percent=0,
        uploads=uploads,
        dataset_id=payload.dataset_id,
        dataset_checksum=dataset_checksum,
        task_type=requested_task_type,
        benchmark_context=benchmark_context,
        stages=(
            []
            if is_adaptive
            else [
                StageExecution(agent_id=aid, output_key=key)
                for aid, key in sequence
            ]
        ),
        experiment_id=experiment_id,
        workspace_id=workspace_id,
    )

    if is_adaptive:
        try:
            plan = plan_route(
                _prepared_context(task),
                [u.format for u in uploads],
            )

            if plan.validation_status != "valid":
                raise HTTPException(
                    422,
                    detail={
                        "code": "invalid_route",
                        "message": plan.validation_error,
                        "routePlan": plan.model_dump(mode="json"),
                    },
                )

        except (ValueError, AgentInputError) as exc:
            raise HTTPException(
                422,
                detail={
                    "code": "invalid_route",
                    "message": str(exc),
                },
            ) from exc

        task.route_plan = plan
        task.task_type = plan.task_type
        task.stages = [
            StageExecution(
                agent_id=aid,
                output_key=CONTRACTS[aid].output,
            )
            for aid in plan.selected_agent_ids
        ]

    if task.execution_mode in (
        TaskExecutionMode.SINGLE,
        TaskExecutionMode.FIXED,
        TaskExecutionMode.ADAPTIVE,
    ):
        task.provenance = build_run_provenance(
            directive=task.directive,
            requested_task_type=requested_task_type,
            dataset_id=task.dataset_id,
            dataset_checksum=task.dataset_checksum,
            benchmark_context=task.benchmark_context,
            uploads=task.uploads,
            configured_model=DEFAULT_MODEL,
            max_output_tokens=DEFAULT_MAX_TOKENS,
            router_version=(
                task.route_plan.router_version
                if task.route_plan is not None
                else None
            ),
        )

    return task


async def enqueue_task(
    task: Task,
    background_tasks: BackgroundTasks,
) -> Task:
    is_pipeline = task.execution_mode == TaskExecutionMode.FIXED

    _TASKS[task.id] = task

    await emit(
        task,
        "simulation_created",
        "Simulation queued",
    )

    if task.route_plan:
        await emit(
            task,
            "route_planned",
            " ".join(task.route_plan.reasons),
            "orchestrator",
        )

    await manager.broadcast(
        "task_created",
        task.model_dump(mode="json"),
        workspace_id=task.workspace_id,
    )

    await register_task_created(task)

    await record_activity(
        "orchestrator" if is_pipeline else "simulation",
        f"Queued simulation {task.id}",
        task=task,
    )

    repository.save(task)

    response = task.model_copy(deep=True)
    background_tasks.add_task(_run_task, task.id)

    return response


async def create_task(
    payload: CreateTaskRequest,
    background_tasks: BackgroundTasks,
    *,
    workspace_id: str | None = None,
):
    """Internal creation boundary retained for coordinator/unit tests."""
    task = prepare_task(payload, workspace_id=workspace_id)
    return await enqueue_task(task, background_tasks)


@router.post("", response_model=Task, status_code=201)
async def create_task_api(
    payload: CreateTaskRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    x_workspace_id: str | None = Header(default=None),
):
    workspace = require_request_permission(
        request, x_workspace_id, Permission.SIMULATION_CREATE
    )
    return await create_task(
        payload,
        background_tasks,
        workspace_id=workspace["id"],
    )


async def _run_stage(task: Task, stage: StageExecution, context: ExecutionContext):
    agent = _IMPLEMENTED_AGENTS.get(stage.agent_id)
    stage.status = "active"
    stage.started_at = now()
    await emit(task, "agent_started", f"{stage.agent_id} started", stage.agent_id)
    await record_activity(stage.agent_id, "Started processing", task=task)
    started = time.perf_counter()
    token = current_execution.set(stage)
    try:
        if agent is None:
            raise NotImplementedError(f"Agent '{stage.agent_id}' is not implemented")
        result = await agent.run(task.directive, context=context)
        if not isinstance(result, str) or not result.strip():
            raise ValueError(f"{stage.agent_id} returned empty output")
        stage.output = result
        stage.status = "completed"
    except (Exception, asyncio.CancelledError) as exc:
        stage.status = "failed"
        stage.error = safe_error(exc)
        if isinstance(exc, AgentInputError):
            stage.input_error = exc.detail
        raise
    finally:
        current_execution.reset(token)
        stage.completed_at = now()
        stage.duration_seconds = time.perf_counter() - started
        completed = sum(s.status == "completed" for s in task.stages)
        task.progress_percent = int(completed / len(task.stages) * 100)
        task.progress_steps = [
            TaskProgressStep(label=f"{s.agent_id}: {s.status}", done=s.status == "completed")
            for s in task.stages
        ]
        event = "agent_completed" if stage.status == "completed" else "agent_failed"
        await record_activity(stage.agent_id, f"Stage {stage.status}", task=task)
        await emit(task, event, f"{stage.agent_id} {stage.status}", stage.agent_id)
    return result


async def _run_pipeline(task: Task) -> str:
    """Preserved execution order; each exact output enters the next context."""
    context = _prepared_context(task)
    if not task.stages:
        task.stages = [StageExecution(agent_id=aid, output_key=key) for aid, key in _PIPELINE_STAGES]
    return await _run_sequence(task, context, _PIPELINE_STAGES)


async def _run_sequence(task: Task, context: ExecutionContext, sequence) -> str:
    """Shared real handoffs for Fixed and validated Adaptive routes."""
    for index, (agent_id, output_key) in enumerate(sequence):
        result = await _run_stage(task, task.stages[index], context)
        context = context.with_output(agent_id, result)
        if index < len(sequence) - 1:
            next_agent = sequence[index + 1][0]
            await record_message(agent_id, next_agent, MessageKind.RESPONSE, result,
                                 task=task, output_key=output_key)
            await emit(task, "message_created", f"{agent_id} → {next_agent}: {output_key}", agent_id)
    return context.output("final_report").text


def _prepared_context(task: Task) -> ExecutionContext:
    """Identical bounded inputs for the fixed path and direct baseline."""
    uploaded_context = None
    if task.uploads:
        uploaded_context = "\n\n".join(
            upload.prepared_context if task.execution_mode == TaskExecutionMode.SINGLE_AGENT
            else f"File: {upload.filename}\n{upload.prepared_context}" for upload in task.uploads
        )
    try:
        return ExecutionContext(original_directive=task.directive, execution_mode=task.execution_mode,
                                task_type=task.task_type, uploaded_context=uploaded_context,
                                benchmark_context=task.benchmark_context,
                                source_text=inline_source(task.directive) if task.execution_mode == TaskExecutionMode.ADAPTIVE else None,
                                route=RouteSelection(selected_agents=task.route_plan.selected_agent_ids,
                                    skipped_agents=task.route_plan.skipped_agent_ids) if task.route_plan else None)
    except ValidationError as exc:
        raise AgentInputError("invalid_context") from exc


async def _execute_mode(task: Task) -> str:
    """One lifecycle/persistence boundary; future modes extend this dispatch."""
    if task.execution_mode == TaskExecutionMode.FIXED:
        return await _run_pipeline(task)
    if task.execution_mode == TaskExecutionMode.SINGLE:
        if not task.stages:
            task.stages = [StageExecution(agent_id="direct", output_key="final_answer")]
        return await _run_stage(task, task.stages[0], _prepared_context(task))
    if task.execution_mode == TaskExecutionMode.SINGLE_AGENT:
        if not task.stages:
            task.stages = [StageExecution(agent_id=task.assigned_agent_id, output_key="output")]
        return await _run_stage(task, task.stages[0], _prepared_context(task))
    if task.execution_mode == TaskExecutionMode.ADAPTIVE:
        context = _prepared_context(task)
        if task.route_plan is None:
            raise ValueError("Adaptive route plan is missing")
        checked = validate_route(task.route_plan, context)
        if checked.validation_status != "valid":
            raise ValueError(checked.validation_error)
        sequence = tuple((aid, CONTRACTS[aid].output) for aid in checked.selected_agent_ids)
        if tuple((s.agent_id, s.output_key) for s in task.stages) != sequence:
            raise ValueError("Adaptive stages do not match the validated route")
        return await _run_sequence(task, context, sequence)
    raise ValueError("Unsupported execution mode")


async def _run_task(task_id: str) -> None:
    task = _TASKS.get(task_id) or get_record(task_id)
    started = time.perf_counter()

    task.execution_started_at = now()
    task.status = TaskStatus.IN_PROGRESS

    coordinator = (
        "orchestrator"
        if task.execution_mode in (
            TaskExecutionMode.FIXED,
            TaskExecutionMode.ADAPTIVE,
        )
        else None
    )

    await emit(
        task,
        "simulation_started",
        "Simulation started",
        coordinator,
    )

    try:
        result = await _execute_mode(task)

        task.output = result
        task.status = TaskStatus.COMPLETED
        task.progress_percent = 100

    except (Exception, asyncio.CancelledError) as exc:
        task.status = TaskStatus.FAILED
        task.error = safe_error(exc)

        if isinstance(exc, AgentInputError):
            task.input_error = exc.detail

        task.output = None

    finally:
        task.completed_at = now()
        task.elapsed_seconds = time.perf_counter() - started
        task.duration_seconds = int(task.elapsed_seconds)

        successful = task.status == TaskStatus.COMPLETED

        if task.execution_mode in (
            TaskExecutionMode.SINGLE,
            TaskExecutionMode.FIXED,
            TaskExecutionMode.ADAPTIVE,
        ):
            task.evaluation = build_run_evaluation(task)

        await record_activity(
            coordinator or "simulation",
            f"Simulation {task.status.value}",
            task=task,
        )

        await emit(
            task,
            "simulation_completed" if successful else "simulation_failed",
            f"Simulation {task.status.value}",
            coordinator,
        )

        await register_task_finished(
            task,
            task.elapsed_seconds,
            successful,
        )

        _TASKS.pop(task.id, None)


def recover_interrupted():
    """A restart cannot resume an in-flight provider call: record an honest failure."""

    for task in repository.list():
        if task.status not in (
            TaskStatus.QUEUED,
            TaskStatus.IN_PROGRESS,
        ):
            continue

        timestamp = now()

        task.status = TaskStatus.FAILED
        task.error = (
            "Server restarted before this simulation completed; "
            "create a new run to retry."
        )
        task.completed_at = timestamp

        if task.execution_started_at:
            task.elapsed_seconds = (
                timestamp - task.execution_started_at
            ).total_seconds()
            task.duration_seconds = int(task.elapsed_seconds)

        for stage in task.stages:
            if stage.status == "active":
                stage.status = "failed"
                stage.error = task.error
                stage.completed_at = timestamp

        task.progress_steps = [
            TaskProgressStep(
                label=f"{stage.agent_id}: {stage.status}",
                done=stage.status == "completed",
            )
            for stage in task.stages
        ]

        if task.execution_mode in (
            TaskExecutionMode.SINGLE,
            TaskExecutionMode.FIXED,
            TaskExecutionMode.ADAPTIVE,
        ):
            task.evaluation = build_run_evaluation(task)

        task.events.append(
            RunEvent(
                id=uuid.uuid4().hex,
                type="simulation_failed",
                timestamp=timestamp,
                text=task.error,
            )
        )

        repository.save(task)
