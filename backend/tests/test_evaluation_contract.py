from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.experiments.evaluation import (
    EVALUATION_PROTOCOL_VERSION,
    QUALITY_RUBRIC,
    QUALITY_RUBRIC_VERSION,
    build_objective_evaluation,
    build_run_evaluation,
    token_measurement,
)
from app.models.schemas import (
    ObjectiveEvaluation,
    QualityCriterion,
    QualityJudgment,
    RunEvaluation,
    StageExecution,
    Task,
    TaskExecutionMode,
    TaskPriority,
    TaskStatus,
)

def task_with_stages(
    *,
    status=TaskStatus.COMPLETED,
    stages=None,
    elapsed_seconds=3.5,
):
    timestamp = datetime.now(timezone.utc)

    return Task(
        id="T-objective-test",
        simulation_id="T-objective-test",
        directive="Evaluate this run.",
        assigned_agent_id="direct",
        status=status,
        priority=TaskPriority.MEDIUM,
        execution_mode=TaskExecutionMode.SINGLE,
        started_at=timestamp,
        created_at=timestamp,
        completed_at=timestamp,
        elapsed_seconds=elapsed_seconds,
        duration_seconds=int(elapsed_seconds or 0),
        progress_percent=100,
        stages=stages or [],
    )


def test_token_measurement_complete():
    timestamp = datetime.now(timezone.utc)

    task = task_with_stages(
        stages=[
            StageExecution(
                agent_id="direct",
                output_key="final_answer",
                started_at=timestamp,
                total_tokens=125,
            )
        ]
    )

    coverage, total = token_measurement(task)

    assert coverage == "complete"
    assert total == 125


def test_token_measurement_partial():
    timestamp = datetime.now(timezone.utc)

    task = task_with_stages(
        stages=[
            StageExecution(
                agent_id="analysis",
                output_key="insights",
                started_at=timestamp,
                total_tokens=100,
            ),
            StageExecution(
                agent_id="report",
                output_key="final_report",
                started_at=timestamp,
                total_tokens=None,
            ),
        ]
    )

    coverage, total = token_measurement(task)

    assert coverage == "partial"
    assert total is None


def test_token_measurement_unavailable():
    timestamp = datetime.now(timezone.utc)

    task = task_with_stages(
        stages=[
            StageExecution(
                agent_id="direct",
                output_key="final_answer",
                started_at=timestamp,
                total_tokens=None,
            )
        ]
    )

    coverage, total = token_measurement(task)

    assert coverage == "unavailable"
    assert total is None


def test_zero_tokens_remain_valid_measurement():
    timestamp = datetime.now(timezone.utc)

    task = task_with_stages(
        stages=[
            StageExecution(
                agent_id="direct",
                output_key="final_answer",
                started_at=timestamp,
                total_tokens=0,
            )
        ]
    )

    coverage, total = token_measurement(task)

    assert coverage == "complete"
    assert total == 0


def test_objective_evaluation_uses_persisted_task_telemetry():
    timestamp = datetime.now(timezone.utc)

    task = task_with_stages(
        elapsed_seconds=4.25,
        stages=[
            StageExecution(
                agent_id="direct",
                output_key="final_answer",
                started_at=timestamp,
                total_tokens=321,
            )
        ],
    )

    evaluation = build_objective_evaluation(task)

    assert evaluation.status == "completed"
    assert evaluation.elapsed_seconds == 4.25
    assert evaluation.agent_invocation_count == 1
    assert evaluation.handoff_count == 0
    assert evaluation.token_coverage == "complete"
    assert evaluation.total_tokens == 321


def test_objective_evaluation_rejects_non_terminal_task():
    task = task_with_stages(
        status=TaskStatus.IN_PROGRESS,
    )

    with pytest.raises(
        ValueError,
        match="terminal task",
    ):
        build_objective_evaluation(task)
        
def criterion(name, score=4, applicable=True):
    return QualityCriterion(
        name=name,
        applicable=applicable,
        score=score if applicable else None,
        rationale="Controlled evaluator rationale.",
    )


def valid_criteria():
    return (
        criterion("task_fulfillment"),
        criterion("completeness"),
        criterion("coherence"),
        criterion("grounding"),
    )


def test_evaluation_protocol_and_rubric_are_versioned():
    assert EVALUATION_PROTOCOL_VERSION == "evaluation-v1"
    assert QUALITY_RUBRIC_VERSION == "quality-rubric-v1"

    assert [item["name"] for item in QUALITY_RUBRIC] == [
        "task_fulfillment",
        "completeness",
        "coherence",
        "grounding",
    ]


def test_objective_evaluation_accepts_complete_token_measurement():
    evidence = ObjectiveEvaluation(
        status="completed",
        elapsed_seconds=2.5,
        agent_invocation_count=3,
        handoff_count=2,
        token_coverage="complete",
        total_tokens=1500,
    )

    assert evidence.total_tokens == 1500


def test_complete_token_coverage_requires_total():
    with pytest.raises(ValidationError):
        ObjectiveEvaluation(
            status="completed",
            elapsed_seconds=2.5,
            agent_invocation_count=3,
            handoff_count=2,
            token_coverage="complete",
            total_tokens=None,
        )


def test_partial_token_coverage_cannot_claim_total():
    with pytest.raises(ValidationError):
        ObjectiveEvaluation(
            status="completed",
            elapsed_seconds=2.5,
            agent_invocation_count=3,
            handoff_count=2,
            token_coverage="partial",
            total_tokens=1500,
        )


def test_non_applicable_grounding_has_no_score():
    item = QualityCriterion(
        name="grounding",
        applicable=False,
        score=None,
        rationale="No reference material was supplied.",
    )

    assert item.score is None


def test_quality_judgment_requires_exact_rubric_order():
    with pytest.raises(ValidationError):
        QualityJudgment(
            evaluator_provider="groq",
            evaluator_model="test-model",
            treatment_blinded=True,
            output_sha256="a" * 64,
            criteria=(
                criterion("completeness"),
                criterion("task_fulfillment"),
                criterion("coherence"),
                criterion("grounding"),
            ),
        )


def test_quality_judgment_is_explicitly_blinded():
    judgment = QualityJudgment(
        evaluator_provider="groq",
        evaluator_model="test-model",
        treatment_blinded=True,
        output_sha256="a" * 64,
        criteria=valid_criteria(),
    )

    dumped = judgment.model_dump(mode="json")

    assert dumped["treatmentBlinded"] is True
    assert "executionMode" not in dumped


def test_run_evaluation_combines_measurement_and_judgment():
    evaluation = RunEvaluation(
        task_id="T-test",
        experiment_id="E-test",
        input_fingerprint="b" * 64,
        evaluated_at=datetime.now(timezone.utc),
        objective=ObjectiveEvaluation(
            status="completed",
            elapsed_seconds=4.2,
            agent_invocation_count=3,
            handoff_count=2,
            token_coverage="complete",
            total_tokens=2000,
        ),
        quality=QualityJudgment(
            evaluator_provider="groq",
            evaluator_model="test-model",
            treatment_blinded=True,
            output_sha256="c" * 64,
            criteria=valid_criteria(),
        ),
    )

    assert evaluation.objective.total_tokens == 2000
    assert evaluation.quality.rubric_version == "quality-rubric-v1"

def test_run_evaluation_uses_task_provenance_fingerprint():
    timestamp = datetime.now(timezone.utc)

    task = task_with_stages(
        stages=[
            StageExecution(
                agent_id="direct",
                output_key="final_answer",
                started_at=timestamp,
                total_tokens=100,
            )
        ]
    )

    from app.models.schemas import RunProvenance

    task.experiment_id = "E-test"
    task.provenance = RunProvenance(
        experiment_protocol_version="experiment-v1",
        input_fingerprint="a" * 64,
        directive_sha256="b" * 64,
        requested_task_type=None,
        dataset_id=None,
        dataset_checksum=None,
        benchmark_context_sha256=None,
        upload_context_sha256=(),
        provider="groq",
        configured_model="test-model",
        max_output_tokens=1024,
        prompt_protocol_version="prompts-v1",
        contracts_version="contracts-v1",
        router_version=None,
    )

    evaluation = build_run_evaluation(task)

    assert evaluation.task_id == task.id
    assert evaluation.experiment_id == "E-test"
    assert evaluation.input_fingerprint == "a" * 64
    assert evaluation.quality is None


def test_run_evaluation_allows_historical_run_without_provenance():
    task = task_with_stages()

    evaluation = build_run_evaluation(task)

    assert evaluation.input_fingerprint is None
    assert evaluation.quality is None


def test_quality_judge_prompt_is_treatment_blinded():
    from app.experiments.evaluation import build_quality_judge_prompt

    task = task_with_stages()
    task.output = "A concise candidate answer."
    task.execution_mode = TaskExecutionMode.ADAPTIVE
    task.assigned_agent_id = "orchestrator"

    prompt = build_quality_judge_prompt(task)

    assert task.id not in prompt
    assert "executionMode" not in prompt
    assert "execution_mode" not in prompt
    assert "assignedAgentId" not in prompt
    assert "assigned_agent_id" not in prompt
    assert "orchestrator" not in prompt
    assert "routePlan" not in prompt
    assert "route_plan" not in prompt


def test_quality_judge_prompt_marks_grounding_not_applicable_without_reference():
    from app.experiments.evaluation import build_quality_judge_prompt

    task = task_with_stages()
    task.output = "A candidate answer."

    prompt = build_quality_judge_prompt(task)

    assert "grounding applicable=false" in prompt
    assert '"score": null' in prompt


def test_quality_parser_accepts_exact_blinded_contract():
    import hashlib

    from app.experiments.evaluation import parse_quality_judgment

    output = "Candidate output"

    payload = """
    {
      "criteria": [
        {
          "name": "task_fulfillment",
          "applicable": true,
          "score": 4,
          "rationale": "Directly addresses the requested task."
        },
        {
          "name": "completeness",
          "applicable": true,
          "score": 4,
          "rationale": "Covers the important requested elements."
        },
        {
          "name": "coherence",
          "applicable": true,
          "score": 5,
          "rationale": "Clear and internally consistent."
        },
        {
          "name": "grounding",
          "applicable": false,
          "score": null,
          "rationale": "No external reference material was supplied."
        }
      ]
    }
    """

    judgment = parse_quality_judgment(
        payload,
        evaluator_provider="groq",
        evaluator_model="test-model",
        output_text=output,
        grounding_applicable=False,
    )

    assert judgment.treatment_blinded is True
    assert judgment.evaluator_provider == "groq"
    assert judgment.evaluator_model == "test-model"
    assert judgment.output_sha256 == hashlib.sha256(
        output.encode("utf-8")
    ).hexdigest()
    assert judgment.criteria[3].applicable is False
    assert judgment.criteria[3].score is None


def test_quality_parser_rejects_markdown_wrapped_json():
    import pytest

    from app.experiments.evaluation import parse_quality_judgment

    with pytest.raises(
        ValueError,
        match="invalid JSON",
    ):
        parse_quality_judgment(
            """```json
            {"criteria": []}
            ```""",
            evaluator_provider="groq",
            evaluator_model="test-model",
            output_text="answer",
            grounding_applicable=False,
        )


def test_quality_parser_rejects_incorrect_grounding_applicability():
    import pytest

    from app.experiments.evaluation import parse_quality_judgment

    payload = """
    {
      "criteria": [
        {
          "name": "task_fulfillment",
          "applicable": true,
          "score": 4,
          "rationale": "Good."
        },
        {
          "name": "completeness",
          "applicable": true,
          "score": 4,
          "rationale": "Good."
        },
        {
          "name": "coherence",
          "applicable": true,
          "score": 4,
          "rationale": "Good."
        },
        {
          "name": "grounding",
          "applicable": true,
          "score": 4,
          "rationale": "Incorrectly claims grounding is applicable."
        }
      ]
    }
    """

    with pytest.raises(
        ValueError,
        match="Grounding applicability",
    ):
        parse_quality_judgment(
            payload,
            evaluator_provider="groq",
            evaluator_model="test-model",
            output_text="answer",
            grounding_applicable=False,
        )


def test_quality_evaluator_uses_shared_llm_client_without_treatment_metadata():
    import asyncio
    from unittest.mock import AsyncMock, patch

    from app.agents.llm_client import LLMResponse
    from app.experiments import evaluation

    task = task_with_stages()
    task.output = "A candidate answer."
    task.execution_mode = TaskExecutionMode.ADAPTIVE

    response = LLMResponse(
        text="""
        {
          "criteria": [
            {
              "name": "task_fulfillment",
              "applicable": true,
              "score": 4,
              "rationale": "Addresses the task."
            },
            {
              "name": "completeness",
              "applicable": true,
              "score": 4,
              "rationale": "Covers the requested content."
            },
            {
              "name": "coherence",
              "applicable": true,
              "score": 5,
              "rationale": "Clear and consistent."
            },
            {
              "name": "grounding",
              "applicable": false,
              "score": null,
              "rationale": "No external reference material."
            }
          ]
        }
        """,
        input_tokens=100,
        output_tokens=50,
        response_time_seconds=0.1,
        model="judge-test-model",
    )

    with patch.object(
        evaluation,
        "call_llm",
        new_callable=AsyncMock,
        return_value=response,
    ) as llm:
        judgment = asyncio.run(
            evaluation.evaluate_quality_judgment(task)
        )

    llm.assert_awaited_once()

    prompt = llm.await_args.kwargs["prompt"]

    assert task.id not in prompt
    assert "executionMode" not in prompt
    assert "routePlan" not in prompt
    assert judgment.evaluator_model == "judge-test-model"
    assert judgment.treatment_blinded is True


def test_quality_evaluation_rejects_failed_run():
    import pytest

    from app.experiments.evaluation import build_quality_judge_prompt

    task = task_with_stages(
        status=TaskStatus.FAILED,
    )
    task.output = None

    with pytest.raises(
        ValueError,
        match="completed task",
    ):
        build_quality_judge_prompt(task)
