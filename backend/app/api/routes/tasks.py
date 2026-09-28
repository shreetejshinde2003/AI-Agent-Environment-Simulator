"""Compatible task API and the V1 sequential five-agent execution engine."""
import asyncio
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.agents.research_agent import ResearchAgent
from app.agents.data_agent import DataAgent
from app.agents.analysis_agent import AnalysisAgent
from app.agents.summarizer_agent import SummarizerAgent
from app.agents.report_agent import ReportAgent
from app.agents.direct_agent import DirectAgent
from app.agents.execution_context import current_execution
from app.api.routes.messages import record_message
from app.api.routes.simulation import record_activity, register_task_created, register_task_finished
from app.core.errors import safe_error
from app.datasets.registry import context_for_dataset
from app.models.schemas import (
    CreateTaskRequest, MessageKind, Task, TaskExecutionMode,
    TaskProgressStep, TaskStatus, StageExecution, RunEvent,
)
from app.storage.database import repository
from app.websocket.manager import manager

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
    await manager.broadcast(event_type, {"simulationId": task.id,
                                         "executionMode": task.execution_mode.value,
                                         **event.model_dump(mode="json")})
    await manager.broadcast("task_updated", task.model_dump(mode="json"))


def get_record(task_id: str) -> Task:
    task = repository.get(task_id)
    if task is None:
        raise HTTPException(404, "Simulation not found")
    return task


@router.get("", response_model=list[Task])
async def list_tasks():
    return repository.list()


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str):
    return get_record(task_id)


@router.post("", response_model=Task, status_code=201)
async def create_task(payload: CreateTaskRequest, background_tasks: BackgroundTasks):
    if not payload.directive.strip():
        raise HTTPException(422, "Directive must not be blank")
    if payload.execution_mode == TaskExecutionMode.ADAPTIVE:
        raise HTTPException(501, detail={"code": "execution_mode_not_implemented",
                                         "executionMode": "adaptive",
                                         "message": "Adaptive execution is not implemented yet."})
    if payload.execution_mode == TaskExecutionMode.SINGLE_AGENT and not payload.assigned_agent_id:
        raise HTTPException(422, "Individual specialist execution requires assignedAgentId")
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
    task_id = f"T-{uuid.uuid4().hex[:12]}"
    is_pipeline = payload.execution_mode == TaskExecutionMode.FIXED
    is_single = payload.execution_mode == TaskExecutionMode.SINGLE
    sequence = _PIPELINE_STAGES if is_pipeline else (
        ("direct", "final_answer") if is_single else (payload.assigned_agent_id, "output"),
    )
    task = Task(
        id=task_id, simulation_id=task_id, directive=payload.directive.strip(),
        assigned_agent_id="orchestrator" if is_pipeline else "direct" if is_single else payload.assigned_agent_id,
        execution_mode=payload.execution_mode, priority=payload.priority,
        status=TaskStatus.QUEUED, started_at=now(), created_at=now(),
        duration_seconds=0, progress_percent=0, uploads=uploads,
        dataset_id=payload.dataset_id, dataset_checksum=dataset_checksum,
        task_type=payload.task_type, benchmark_context=benchmark_context,
        stages=[StageExecution(agent_id=aid, output_key=key) for aid, key in sequence],
    )
    _TASKS[task.id] = task
    await emit(task, "simulation_created", "Simulation queued")
    await manager.broadcast("task_created", task.model_dump(mode="json"))
    await register_task_created()
    await record_activity("orchestrator" if is_pipeline else "simulation",
                          f"Queued simulation {task.id}", task=task)
    repository.save(task)
    # Freeze the queued HTTP response before background execution mutates state.
    response = task.model_copy(deep=True)
    background_tasks.add_task(_run_task, task.id)
    return response


async def _run_stage(task: Task, stage: StageExecution, context: dict):
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
    for index, (agent_id, output_key) in enumerate(_PIPELINE_STAGES):
        result = await _run_stage(task, task.stages[index], context)
        context[output_key] = result
        if index < len(_PIPELINE_STAGES) - 1:
            next_agent = _PIPELINE_STAGES[index + 1][0]
            await record_message(agent_id, next_agent, MessageKind.RESPONSE, result,
                                 task=task, output_key=output_key)
            await emit(task, "message_created", f"{agent_id} → {next_agent}: {output_key}", agent_id)
    return context["final_report"]


def _prepared_context(task: Task) -> dict:
    """Identical bounded inputs for the fixed path and direct baseline."""
    context = {}
    if task.uploads:
        context["uploaded_context"] = "\n\n".join(
            f"File: {upload.filename}\n{upload.prepared_context}" for upload in task.uploads
        )
    if task.benchmark_context:
        context["benchmark_context"] = task.benchmark_context
    return context


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
        context = {}
        if task.uploads:
            context["uploaded_context"] = "\n\n".join(u.prepared_context for u in task.uploads)
        if task.benchmark_context:
            context["benchmark_context"] = task.benchmark_context
        return await _run_stage(task, task.stages[0], context)
    raise NotImplementedError("Adaptive execution is not implemented yet")


async def _run_task(task_id: str) -> None:
    task = _TASKS.get(task_id) or get_record(task_id)
    started = time.perf_counter()
    task.execution_started_at = now()
    task.status = TaskStatus.IN_PROGRESS
    coordinator = "orchestrator" if task.execution_mode == TaskExecutionMode.FIXED else None
    await emit(task, "simulation_started", "Simulation started", coordinator)
    try:
        result = await _execute_mode(task)
        task.output = result
        task.status = TaskStatus.COMPLETED
        task.progress_percent = 100
    except (Exception, asyncio.CancelledError) as exc:
        task.status = TaskStatus.FAILED
        task.error = safe_error(exc)
        task.output = None
    finally:
        task.completed_at = now()
        task.elapsed_seconds = time.perf_counter() - started
        task.duration_seconds = int(task.elapsed_seconds)
        successful = task.status == TaskStatus.COMPLETED
        await record_activity(coordinator or "simulation", f"Simulation {task.status.value}", task=task)
        await emit(task, "simulation_completed" if successful else "simulation_failed",
                   f"Simulation {task.status.value}", coordinator)
        await register_task_finished(task.elapsed_seconds, successful)
        _TASKS.pop(task.id, None)


def recover_interrupted():
    """A restart cannot resume an in-flight provider call: record an honest failure."""
    for task in repository.list():
        if task.status not in (TaskStatus.QUEUED, TaskStatus.IN_PROGRESS):
            continue
        timestamp = now()
        task.status = TaskStatus.FAILED
        task.error = "Server restarted before this simulation completed; create a new run to retry."
        task.completed_at = timestamp
        if task.execution_started_at:
            task.elapsed_seconds = (timestamp - task.execution_started_at).total_seconds()
            task.duration_seconds = int(task.elapsed_seconds)
        for stage in task.stages:
            if stage.status == "active":
                stage.status = "failed"
                stage.error = task.error
                stage.completed_at = timestamp
        task.progress_steps = [
            TaskProgressStep(label=f"{s.agent_id}: {s.status}", done=s.status == "completed")
            for s in task.stages
        ]
        task.events.append(RunEvent(id=uuid.uuid4().hex, type="simulation_failed",
                                   timestamp=timestamp, text=task.error))
        repository.save(task)
