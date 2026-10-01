"""Versioned contracts and rubric definitions for research evaluation."""

EVALUATION_PROTOCOL_VERSION = "evaluation-v1"
QUALITY_RUBRIC_VERSION = "quality-rubric-v1"
from datetime import datetime, timezone
from app.models.schemas import (
    ObjectiveEvaluation,
    RunEvaluation,
    Task,
    TaskStatus,
)
QUALITY_RUBRIC = (
    {
        "name": "task_fulfillment",
        "description": (
            "How well the response directly fulfills the user's requested task."
        ),
    },
    {
        "name": "completeness",
        "description": (
            "Whether the response covers the important requested components "
            "without material omissions."
        ),
    },
    {
        "name": "coherence",
        "description": (
            "Whether the response is logically organized, internally consistent, "
            "and understandable."
        ),
    },
    {
        "name": "grounding",
        "description": (
            "Whether claims appropriately use and remain consistent with supplied "
            "reference material when such material is available."
        ),
    },
)
def token_measurement(task: Task) -> tuple[str, int | None]:
    """Return the same token-coverage semantics used by simulation metrics."""

    started = [
        stage
        for stage in task.stages
        if stage.started_at is not None
    ]

    measured = [
        stage
        for stage in started
        if stage.total_tokens is not None
    ]

    if not started or not measured:
        return "unavailable", None

    if len(measured) < len(started):
        return "partial", None

    return "complete", sum(
        stage.total_tokens
        for stage in measured
    )


def build_objective_evaluation(task: Task) -> ObjectiveEvaluation:
    """Build measured evaluation evidence without calling an LLM."""

    if task.status not in (
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
    ):
        raise ValueError(
            "Objective evaluation requires a terminal task."
        )

    coverage, total_tokens = token_measurement(task)

    return ObjectiveEvaluation(
        status=task.status.value,
        elapsed_seconds=task.elapsed_seconds,
        agent_invocation_count=task.agent_invocation_count,
        handoff_count=task.handoff_count,
        token_coverage=coverage,
        total_tokens=total_tokens,
    )
def build_run_evaluation(task: Task) -> RunEvaluation:
    """Attach deterministic terminal-run evidence; quality is evaluated separately."""

    objective = build_objective_evaluation(task)

    return RunEvaluation(
        task_id=task.id,
        experiment_id=task.experiment_id,
        input_fingerprint=(
            task.provenance.input_fingerprint
            if task.provenance is not None
            else None
        ),
        evaluated_at=datetime.now(timezone.utc),
        objective=objective,
        quality=None,
    )