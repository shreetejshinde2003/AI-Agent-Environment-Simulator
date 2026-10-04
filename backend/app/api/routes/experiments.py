"""Controlled matched experiments across Single, Fixed and Adaptive modes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.api.routes.tasks import enqueue_task, prepare_task
from app.api.routes.workspaces import require_request_permission
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
    )

    fixed = prepare_task(
        CreateTaskRequest(
            **common,
            execution_mode=TaskExecutionMode.FIXED,
        ),
        experiment_id=experiment_id,
        workspace_id=workspace["id"],
    )

    adaptive = prepare_task(
        CreateTaskRequest(
            **common,
            execution_mode=TaskExecutionMode.ADAPTIVE,
        ),
        experiment_id=experiment_id,
        workspace_id=workspace["id"],
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