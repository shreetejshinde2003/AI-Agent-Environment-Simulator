"""Controlled matched experiments across Single, Fixed and Adaptive modes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.api.routes.tasks import enqueue_task, prepare_task
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
):
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
    )

    fixed = prepare_task(
        CreateTaskRequest(
            **common,
            execution_mode=TaskExecutionMode.FIXED,
        ),
        experiment_id=experiment_id,
    )

    adaptive = prepare_task(
        CreateTaskRequest(
            **common,
            execution_mode=TaskExecutionMode.ADAPTIVE,
        ),
        experiment_id=experiment_id,
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