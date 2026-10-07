"""Controlled matched experiments across Single, Fixed and Adaptive modes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.api.routes.tasks import enqueue_task, prepare_task
from app.api.routes.workspaces import require_request_permission, request_user_id
from app.security.rbac import Permission
from app.models.schemas import (
    CreateMatchedExperimentRequest,
    CreateTaskRequest,
    MatchedExperiment,
    MatchedExperimentRun,
    TaskExecutionMode,
)

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.post("/matched", response_model=MatchedExperiment, status_code=201)
async def create_matched_experiment(
    payload: CreateMatchedExperimentRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    x_workspace_id: str | None = Header(default=None),
):
    workspace = require_request_permission(
        request, x_workspace_id, Permission.SIMULATION_CREATE
    )
    experiment_id = f"E-{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc)
    user_id = request_user_id(request)

    common = dict(
        directive=payload.directive,
        title=payload.title,
        priority=payload.priority,
        upload_ids=payload.upload_ids,
        dataset_id=payload.dataset_id,
        task_type=payload.task_type,
    )

    single = prepare_task(
        CreateTaskRequest(
            **common,
            execution_mode=TaskExecutionMode.SINGLE,
        ),
        experiment_id=experiment_id,
        workspace_id=workspace["id"],
        user_id=user_id,
    )

    fixed = prepare_task(
        CreateTaskRequest(
            **common,
            execution_mode=TaskExecutionMode.FIXED,
        ),
        experiment_id=experiment_id,
        workspace_id=workspace["id"],
        user_id=user_id,
    )

    adaptive = prepare_task(
        CreateTaskRequest(
            **common,
            execution_mode=TaskExecutionMode.ADAPTIVE,
        ),
        experiment_id=experiment_id,
        workspace_id=workspace["id"],
        user_id=user_id,
    )

    tasks = (single, fixed, adaptive)

    fingerprints = {
        task.provenance.input_fingerprint
        for task in tasks
        if task.provenance is not None
    }

    if len(fingerprints) != 1:
        raise HTTPException(
            500,
            detail={
                "code": "matched_input_invariant_failed",
                "message": (
                    "Matched experiment runs did not produce one "
                    "shared input fingerprint."
                ),
            },
        )

    input_fingerprint = next(iter(fingerprints))

    responses = []
    for task in tasks:
        responses.append(
            await enqueue_task(
                task,
                background_tasks,
                user_id=user_id,
            )
        )

    return MatchedExperiment(
        experiment_id=experiment_id,
        created_at=created_at,
        input_fingerprint=input_fingerprint,
        runs=(
            MatchedExperimentRun(
                execution_mode="single",
                task_id=responses[0].id,
            ),
            MatchedExperimentRun(
                execution_mode="fixed",
                task_id=responses[1].id,
            ),
            MatchedExperimentRun(
                execution_mode="adaptive",
                task_id=responses[2].id,
            ),
        ),
    )

# Phase 9 uses Task payloads, StageExecution and RoutePlan, without another engine.
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.experiments.research import catalog, canonical_hash, comparison, current_configuration, report, HUMAN_RUBRIC
from app.models.schemas import ResearchExperimentInput, ResearchTrial, HumanRubricInput
from app.storage.database import repository


def research_records(request, workspace_id, experiment_id=None, permission=Permission.SIMULATION_VIEW):
    workspace = require_request_permission(request, workspace_id, permission)
    user_id = request_user_id(request)
    runs = repository.research_tasks(workspace_id=workspace["id"], user_id=user_id, experiment_id=experiment_id)
    if experiment_id and not runs:
        raise HTTPException(404, "Research experiment unavailable")
    return workspace, user_id, runs


@router.get("/benchmarks")
async def get_benchmarks(request: Request, x_workspace_id: str | None = Header(default=None)):
    require_request_permission(request, x_workspace_id, Permission.SIMULATION_VIEW)
    return {"version": "1", "cases": [case.model_dump(mode="json") for case in catalog()], "humanRubric": HUMAN_RUBRIC,
            "configuration": current_configuration().model_dump(mode="json"), "executionEnabled": settings.RESEARCH_LIVE_ENABLED,
            "maxRuns": 45, "maxRepetitions": 5}


async def admit_research(payload, background_tasks, *, workspace_id, user_id, parent=None):
    if not settings.RESEARCH_LIVE_ENABLED:
        raise HTTPException(403, "Research provider execution is disabled; explicit live-provider approval is required")
    cases = {case.id: case for case in catalog()}
    if any(bid not in cases or any(mode not in cases[bid].modes for mode in payload.modes) for bid in payload.benchmark_ids):
        raise HTTPException(422, "Unknown benchmark or unsupported mode")
    config = current_configuration()
    experiment_id = "E-" + uuid.uuid4().hex[:12]
    prepared = []
    # Balanced rotation avoids always placing Single first. BackgroundTasks run sequentially.
    for trial in range(1, payload.repetitions + 1):
        order = payload.modes[(trial - 1) % len(payload.modes):] + payload.modes[:(trial - 1) % len(payload.modes)]
        for bid in payload.benchmark_ids:
            case = cases[bid]
            for mode in order:
                task = prepare_task(CreateTaskRequest(directive=case.execution_directive, title=f"{case.title} · {mode} · trial {trial}",
                    task_type=case.task_type, execution_mode=mode), experiment_id=experiment_id, workspace_id=workspace_id, user_id=user_id)
                prepared.append((task, case, trial))
    run_ids = tuple(t.id for t, _, _ in prepared)
    for task, case, trial in prepared:
        task.research = ResearchTrial(experiment=payload, configuration=config, benchmark=case,
            benchmark_sha256=canonical_hash(case.model_dump(mode="json")), trial_number=trial, run_ids=run_ids, parent_experiment_id=parent)
    # One atomic admission: a failure cannot leave an unidentifiable partial experiment.
    repository.save_research_group([t for t, _, _ in prepared], workspace_id=workspace_id, user_id=user_id)
    for task, _, _ in prepared:
        await enqueue_task(task, background_tasks, user_id=user_id)
    return comparison([t for t, _, _ in prepared])


@router.post("/research", status_code=201)
async def create_research(payload: ResearchExperimentInput, background_tasks: BackgroundTasks, request: Request,
                          x_workspace_id: str | None = Header(default=None)):
    workspace = require_request_permission(request, x_workspace_id, Permission.SIMULATION_CREATE)
    return await admit_research(payload, background_tasks, workspace_id=workspace["id"], user_id=request_user_id(request))


@router.get("/research")
async def list_research(request: Request, x_workspace_id: str | None = Header(default=None)):
    _, _, runs = research_records(request, x_workspace_id)
    groups = {}
    for task in runs:
        groups.setdefault(task.experiment_id, []).append(task)
    return [{"experimentId": eid, "purpose": group[0].research.experiment.purpose,
             "createdAt": group[0].created_at.isoformat(), "recordedRuns": len(group), "expectedRuns": len(group[0].research.run_ids)}
            for eid, group in reversed(list(groups.items()))]


@router.get("/research/{experiment_id}")
async def get_research(experiment_id: str, request: Request, x_workspace_id: str | None = Header(default=None)):
    _, _, runs = research_records(request, x_workspace_id, experiment_id)
    return comparison(runs)


@router.get("/research/{experiment_id}/report")
async def export_research(experiment_id: str, request: Request, x_workspace_id: str | None = Header(default=None)):
    _, _, runs = research_records(request, x_workspace_id, experiment_id, Permission.SIMULATION_EXPORT)
    return JSONResponse(report(runs), headers={"Content-Disposition": f'attachment; filename="{runs[0].experiment_id}-report.json"'})


@router.post("/research/{experiment_id}/rerun", status_code=201)
async def rerun_research(experiment_id: str, background_tasks: BackgroundTasks, request: Request,
                         x_workspace_id: str | None = Header(default=None)):
    workspace, user_id, runs = research_records(request, x_workspace_id, experiment_id, Permission.SIMULATION_CREATE)
    if not comparison(runs)["comparable"]:
        raise HTTPException(409, "Original experiment evidence is incomplete or inconsistent; create a new experiment")
    recorded = runs[0].research
    active = {c.id: c for c in catalog()}
    if recorded.configuration != current_configuration() or any(active.get(t.research.benchmark.id) != t.research.benchmark for t in runs):
        raise HTTPException(409, "Configuration or benchmark has changed; create a new experiment instead")
    return await admit_research(recorded.experiment, background_tasks, workspace_id=workspace["id"], user_id=user_id, parent=experiment_id)


@router.post("/research/{experiment_id}/runs/{task_id}/human-review")
async def human_review(experiment_id: str, task_id: str, payload: HumanRubricInput, request: Request,
                       x_workspace_id: str | None = Header(default=None)):
    workspace, user_id, runs = research_records(request, x_workspace_id, experiment_id, Permission.SIMULATION_EVALUATE)
    if task_id not in {t.id for t in runs}:
        raise HTTPException(404, "Research run unavailable")
    try:
        repository.append_research_review(task_id, payload, workspace_id=workspace["id"], user_id=user_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    _, _, refreshed = research_records(request, x_workspace_id, experiment_id)
    return comparison(refreshed)
