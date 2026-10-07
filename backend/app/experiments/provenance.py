"""Deterministic provenance helpers for controlled research experiments.

This module records enough immutable evidence to determine whether runs
received the same experimental inputs. It does not execute agents, call a
provider, choose a route, or evaluate output quality.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from app.models.schemas import RunProvenance, UploadedContext


EXPERIMENT_PROTOCOL_VERSION = "experiment-v1"
PROMPT_PROTOCOL_VERSION = "prompts-v2-intent"
CONTRACTS_VERSION = "contracts-v2-output"
PROVIDER_NAME = "groq"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def optional_sha256_text(value: str | None) -> str | None:
    return sha256_text(value) if value is not None else None


def _canonical_json(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _upload_material(upload: UploadedContext) -> dict[str, str]:
    """Represent the bounded upload material that can affect execution.

    Filename is included because the research execution modes expose the
    filename alongside prepared context. Format is included because Adaptive
    routing can use the supplied upload formats.
    """
    return {
        "filename": upload.filename,
        "format": upload.format,
        "preparedContext": upload.prepared_context,
    }


def upload_context_sha256(upload: UploadedContext) -> str:
    return sha256_text(_canonical_json(_upload_material(upload)))


def build_input_fingerprint(
    *,
    directive: str,
    requested_task_type: str | None,
    dataset_id: str | None,
    dataset_checksum: str | None,
    benchmark_context: str | None,
    uploads: Sequence[UploadedContext],
) -> str:
    """Hash experimental input only.

    Execution mode is intentionally excluded because Single, Fixed and
    Adaptive are the treatments being compared. Presentation-only values such
    as title, run ID and timestamps are also excluded.
    """
    material = {
        # Task creation strips the directive before execution.
        "directive": directive.strip(),
        # Preserve task type exactly because the current execution contract
        # stores it without normalization.
        "requestedTaskType": requested_task_type,
        "datasetId": dataset_id,
        "datasetChecksum": dataset_checksum,
        "benchmarkContext": benchmark_context,
        # Preserve upload order because execution preserves it.
        "uploads": [_upload_material(upload) for upload in uploads],
    }
    return sha256_text(_canonical_json(material))


def build_run_provenance(
    *,
    directive: str,
    requested_task_type: str | None,
    dataset_id: str | None,
    dataset_checksum: str | None,
    benchmark_context: str | None,
    uploads: Sequence[UploadedContext],
    configured_model: str,
    max_output_tokens: int,
    router_version: str | None = None,
) -> RunProvenance:
    normalized_directive = directive.strip()

    return RunProvenance(
        experiment_protocol_version=EXPERIMENT_PROTOCOL_VERSION,
        input_fingerprint=build_input_fingerprint(
            directive=normalized_directive,
            requested_task_type=requested_task_type,
            dataset_id=dataset_id,
            dataset_checksum=dataset_checksum,
            benchmark_context=benchmark_context,
            uploads=uploads,
        ),
        directive_sha256=sha256_text(normalized_directive),
        requested_task_type=requested_task_type,
        dataset_id=dataset_id,
        dataset_checksum=dataset_checksum,
        benchmark_context_sha256=optional_sha256_text(benchmark_context),
        upload_context_sha256=tuple(
            upload_context_sha256(upload) for upload in uploads
        ),
        provider=PROVIDER_NAME,
        configured_model=configured_model,
        max_output_tokens=max_output_tokens,
        prompt_protocol_version=PROMPT_PROTOCOL_VERSION,
        contracts_version=CONTRACTS_VERSION,
        router_version=router_version,
    )