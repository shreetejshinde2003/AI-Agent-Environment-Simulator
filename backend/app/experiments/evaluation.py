"""Versioned deterministic and blinded research evaluation."""

import hashlib
import json
from datetime import datetime, timezone

from app.agents.llm_client import call_llm
from app.models.schemas import (
    ObjectiveEvaluation,
    QualityCriterion,
    QualityJudgment,
    RunEvaluation,
    Task,
    TaskStatus,
)


EVALUATION_PROTOCOL_VERSION = "evaluation-v1"
QUALITY_RUBRIC_VERSION = "quality-rubric-v1"

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

QUALITY_JUDGE_SYSTEM_PROMPT = """You are a blinded research evaluator.

Evaluate only the quality of the candidate response relative to the supplied
task and, when present, supplied reference material.

You are not given the execution architecture that produced the response.
Do not infer, reward, or penalize any implementation architecture, routing
strategy, number of agents, latency, token usage, or computational cost.

Use the rubric exactly as supplied.

Scores:
1 = seriously inadequate
2 = major weaknesses
3 = adequate but meaningful weaknesses remain
4 = strong with minor weaknesses
5 = excellent for the criterion

Return ONLY one valid JSON object.
Do not use markdown fences.
Do not add commentary before or after the JSON.
"""


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


def _reference_material(task: Task) -> str | None:
    """Return only prepared/bounded reference context permitted for judging."""

    parts: list[str] = []

    if task.benchmark_context:
        parts.append(
            "Validated benchmark context:\n"
            + task.benchmark_context.strip()
        )

    for upload in task.uploads:
        prepared = (upload.prepared_context or "").strip()

        if not prepared:
            continue

        parts.append(
            f"Uploaded reference: {upload.filename}\n{prepared}"
        )

    if not parts:
        return None

    return "\n\n".join(parts)


def build_quality_judge_prompt(task: Task) -> str:
    """Build a treatment-blinded quality-evaluation prompt."""

    if task.status != TaskStatus.COMPLETED:
        raise ValueError(
            "Quality evaluation requires a completed task."
        )

    if not task.output or not task.output.strip():
        raise ValueError(
            "Quality evaluation requires a non-empty task output."
        )

    reference = _reference_material(task)
    grounding_applicable = reference is not None

    rubric_lines = "\n".join(
        f"- {item['name']}: {item['description']}"
        for item in QUALITY_RUBRIC
    )

    reference_section = (
        reference
        if reference is not None
        else (
            "No external reference material was supplied. "
            "The grounding criterion is not applicable."
        )
    )

    grounding_instruction = (
        "Set grounding applicable=true and provide a score from 1 to 5."
        if grounding_applicable
        else "Set grounding applicable=false and score=null."
    )

    return f"""Evaluate the candidate response below.

ORIGINAL TASK:
{task.directive}

REFERENCE MATERIAL:
{reference_section}

CANDIDATE RESPONSE:
{task.output}

QUALITY RUBRIC:
{rubric_lines}

GROUNDING RULE:
{grounding_instruction}

Return exactly this JSON shape:

{{
  "criteria": [
    {{
      "name": "task_fulfillment",
      "applicable": true,
      "score": 1,
      "rationale": "brief reason"
    }},
    {{
      "name": "completeness",
      "applicable": true,
      "score": 1,
      "rationale": "brief reason"
    }},
    {{
      "name": "coherence",
      "applicable": true,
      "score": 1,
      "rationale": "brief reason"
    }},
    {{
      "name": "grounding",
      "applicable": {"true" if grounding_applicable else "false"},
      "score": {"1" if grounding_applicable else "null"},
      "rationale": "brief reason"
    }}
  ]
}}

Rules:
- Use integer scores only.
- Use scores from 1 through 5.
- Keep every rationale concise.
- Preserve the exact criterion order shown above.
- Do not add additional criteria.
- Do not include architecture, routing, agent, latency, or token judgments.
"""


def parse_quality_judgment(
    text: str,
    *,
    evaluator_provider: str,
    evaluator_model: str,
    output_text: str,
    grounding_applicable: bool,
) -> QualityJudgment:
    """Strictly validate the evaluator's JSON response."""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Quality evaluator returned invalid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            "Quality evaluator response must be one JSON object."
        )

    if set(payload) != {"criteria"}:
        raise ValueError(
            "Quality evaluator response contains unexpected fields."
        )

    raw_criteria = payload.get("criteria")

    if not isinstance(raw_criteria, list):
        raise ValueError(
            "Quality evaluator criteria must be a JSON array."
        )

    if len(raw_criteria) != 4:
        raise ValueError(
            "Quality evaluator must return exactly four criteria."
        )

    criteria = tuple(
        QualityCriterion.model_validate(item)
        for item in raw_criteria
    )

    grounding = criteria[3]

    if grounding.name != "grounding":
        raise ValueError(
            "Grounding must be the fourth rubric criterion."
        )

    if grounding.applicable != grounding_applicable:
        raise ValueError(
            "Grounding applicability does not match supplied reference material."
        )

    output_sha256 = hashlib.sha256(
        output_text.encode("utf-8")
    ).hexdigest()

    return QualityJudgment(
        evaluation_protocol_version=EVALUATION_PROTOCOL_VERSION,
        rubric_version=QUALITY_RUBRIC_VERSION,
        evaluator_provider=evaluator_provider,
        evaluator_model=evaluator_model,
        treatment_blinded=True,
        output_sha256=output_sha256,
        criteria=criteria,
    )


async def evaluate_quality_judgment(task: Task) -> QualityJudgment:
    """Run one treatment-blinded LLM quality evaluation."""

    prompt = build_quality_judge_prompt(task)
    reference = _reference_material(task)

    response = await call_llm(
        prompt=prompt,
        system=QUALITY_JUDGE_SYSTEM_PROMPT,
    )

    return parse_quality_judgment(
        response.text,
        evaluator_provider="groq",
        evaluator_model=response.model,
        output_text=task.output or "",
        grounding_applicable=reference is not None,
    )
