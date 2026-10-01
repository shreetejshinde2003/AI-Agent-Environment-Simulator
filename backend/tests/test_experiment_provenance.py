from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.experiments.provenance import (
    build_input_fingerprint,
    build_run_provenance,
)
from app.models.schemas import (
    CreateMatchedExperimentRequest,
    MatchedExperiment,
    MatchedExperimentRun,
    Task,
    UploadedContext,
)



def upload(
    *,
    filename="notes.txt",
    format="txt",
    prepared_context="bounded reference context",
):
    return UploadedContext(
        id="U-test",
        filename=filename,
        format=format,
        size_bytes=100,
        created_at=datetime.now(timezone.utc),
        preview="preview",
        prepared_context=prepared_context,
    )


def fingerprint(
    *,
    directive="Analyze these observations.",
    task_type="analysis",
    dataset_id="employee_small",
    dataset_checksum="dataset-checksum-a",
    benchmark_context="bounded benchmark aggregate",
    uploads=None,
):
    return build_input_fingerprint(
        directive=directive,
        requested_task_type=task_type,
        dataset_id=dataset_id,
        dataset_checksum=dataset_checksum,
        benchmark_context=benchmark_context,
        uploads=uploads if uploads is not None else [upload()],
    )


def test_identical_experimental_input_has_identical_fingerprint():
    assert fingerprint() == fingerprint()


def test_directive_change_changes_fingerprint():
    assert fingerprint() != fingerprint(
        directive="Analyze these different observations."
    )


def test_dataset_version_change_changes_fingerprint():
    assert fingerprint() != fingerprint(
        dataset_checksum="dataset-checksum-b"
    )


def test_benchmark_context_change_changes_fingerprint():
    assert fingerprint() != fingerprint(
        benchmark_context="different bounded benchmark aggregate"
    )


def test_upload_content_change_changes_fingerprint():
    assert fingerprint() != fingerprint(
        uploads=[upload(prepared_context="different prepared context")]
    )


def test_upload_format_change_changes_fingerprint():
    assert fingerprint() != fingerprint(
        uploads=[upload(format="json")]
    )


def test_upload_filename_change_changes_fingerprint():
    assert fingerprint() != fingerprint(
        uploads=[upload(filename="different.txt")]
    )


def test_upload_order_is_part_of_actual_input():
    first = upload(filename="first.txt", prepared_context="A")
    second = upload(filename="second.txt", prepared_context="B")

    assert fingerprint(uploads=[first, second]) != fingerprint(
        uploads=[second, first]
    )


def test_requested_task_type_change_changes_fingerprint():
    assert fingerprint() != fingerprint(task_type="reporting")


def test_execution_treatment_is_not_part_of_input_fingerprint():
    # build_input_fingerprint deliberately accepts no execution_mode argument.
    # Therefore Single, Fixed and Adaptive can share an input fingerprint.
    single_like = fingerprint()
    fixed_like = fingerprint()
    adaptive_like = fingerprint()

    assert single_like == fixed_like == adaptive_like


def test_presentation_title_cannot_change_input_fingerprint():
    # Title is deliberately not an argument to build_input_fingerprint.
    before = fingerprint()
    after = fingerprint()

    assert before == after


def test_run_provenance_records_protocol_without_raw_input_duplication():
    item = upload()

    provenance = build_run_provenance(
        directive=" Analyze these observations. ",
        requested_task_type="analysis",
        dataset_id="employee_small",
        dataset_checksum="dataset-checksum-a",
        benchmark_context="bounded benchmark aggregate",
        uploads=[item],
        configured_model="openai/gpt-oss-120b",
        max_output_tokens=1024,
        router_version="rules-v1",
    )

    assert provenance.experiment_protocol_version == "experiment-v1"
    assert provenance.prompt_protocol_version == "prompts-v1"
    assert provenance.contracts_version == "contracts-v1"
    assert provenance.provider == "groq"
    assert provenance.configured_model == "openai/gpt-oss-120b"
    assert provenance.max_output_tokens == 1024
    assert provenance.router_version == "rules-v1"

    assert len(provenance.input_fingerprint) == 64
    assert len(provenance.directive_sha256) == 64
    assert len(provenance.upload_context_sha256) == 1

    dumped = provenance.model_dump(mode="json")
    serialized = str(dumped)

    assert "Analyze these observations." not in serialized
    assert "bounded benchmark aggregate" not in serialized
    assert "bounded reference context" not in serialized


def test_provenance_fingerprint_ignores_protocol_treatment_metadata():
    common = dict(
        directive="Analyze these observations.",
        requested_task_type="analysis",
        dataset_id="employee_small",
        dataset_checksum="dataset-checksum-a",
        benchmark_context="bounded benchmark aggregate",
        uploads=[upload()],
        max_output_tokens=1024,
    )

    single = build_run_provenance(
        **common,
        configured_model="openai/gpt-oss-120b",
        router_version=None,
    )
    adaptive = build_run_provenance(
        **common,
        configured_model="openai/gpt-oss-120b",
        router_version="rules-v1",
    )

    assert single.input_fingerprint == adaptive.input_fingerprint
def test_matched_experiment_request_has_no_execution_mode_override():
    request = CreateMatchedExperimentRequest(
        directive="Compare the same input across research modes",
    )

    payload = request.model_dump(mode="json")

    assert "executionMode" not in payload
    assert "assignedAgentId" not in payload


def test_matched_experiment_contract_has_exact_three_research_modes():
    fingerprint = "a" * 64

    experiment = MatchedExperiment(
        experiment_id="E-test123",
        created_at=datetime.now(timezone.utc),
        input_fingerprint=fingerprint,
        runs=(
            MatchedExperimentRun(
                execution_mode="single",
                task_id="T-single",
            ),
            MatchedExperimentRun(
                execution_mode="fixed",
                task_id="T-fixed",
            ),
            MatchedExperimentRun(
                execution_mode="adaptive",
                task_id="T-adaptive",
            ),
        ),
    )

    assert experiment.input_fingerprint == fingerprint
    assert [run.execution_mode for run in experiment.runs] == [
        "single",
        "fixed",
        "adaptive",
    ]


def test_matched_experiment_run_rejects_legacy_specialist_mode():
    with pytest.raises(ValidationError):
        MatchedExperimentRun(
            execution_mode="single_agent",
            task_id="T-legacy",
        )


def test_historical_task_without_experiment_id_remains_valid():
    from app.models.schemas import (
        TaskPriority,
        TaskStatus,
    )

    snapshot = {
        "id": "T-historical",
        "directive": "Historical task",
        "assignedAgentId": "direct",
        "status": TaskStatus.COMPLETED,
        "priority": TaskPriority.MEDIUM,
        "executionMode": "single",
        "startedAt": datetime.now(timezone.utc),
        "durationSeconds": 1,
        "progressPercent": 100,
    }

    restored = Task.model_validate(snapshot)

    assert restored.experiment_id is None