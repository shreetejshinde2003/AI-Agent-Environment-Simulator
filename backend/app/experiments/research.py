"""Evidence-derived, descriptive research comparisons. No provider calls here."""
import json
import math
import statistics
from importlib.metadata import version
from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.experiments.provenance import sha256_text, build_input_fingerprint
from app.models.schemas import BenchmarkCase, ResearchConfiguration

CATALOG_PATH = Path(__file__).resolve().parents[2] / "database/benchmarks/research-v1.json"
DIMENSIONS = ("correctness", "relevance", "completeness", "clarity", "groundedness", "concision", "source_consistency")
HUMAN_RUBRIC = {
    "version": "human-v1",
    "dimensions": DIMENSIONS,
    "anchors": {"1": "Materially wrong or missing", "2": "Major weaknesses", "3": "Adequate with meaningful omissions", "4": "Strong with minor weaknesses", "5": "Fully meets the criterion"},
    "limitations": "Subjective human assessment, not ground truth. Evaluate source consistency and unnecessary verbosity explicitly. All seven dimensions required; equal-weight mean is descriptive only.",
}


def canonical_hash(value):
    return sha256_text(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def catalog():
    cases = tuple(BenchmarkCase.model_validate(row) for row in json.loads(CATALOG_PATH.read_text()))
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Duplicate benchmark identity")
    return cases


def current_configuration():
    from app.experiments.demo_budget import bounded_demo, MAX_OUTPUT_TOKENS
    from app.api.routes.tasks import _IMPLEMENTED_AGENTS
    from app.agents.llm_client import DEFAULT_MODEL, DEFAULT_MAX_TOKENS
    root = Path(__file__).resolve().parents[1]
    files = (sorted((root / "agents").glob("*.py"))
             + sorted((root / "experiments").glob("*.py"))
             + [root / "api/routes/tasks.py", root / "api/routes/experiments.py",
                root / "models/schemas.py", root / "storage/database.py"])
    return ResearchConfiguration(
        agent_models=tuple((aid, agent.MODEL or DEFAULT_MODEL) for aid, agent in sorted(_IMPLEMENTED_AGENTS.items())),
        max_output_tokens=MAX_OUTPUT_TOKENS if bounded_demo() else DEFAULT_MAX_TOKENS,
        retry_policy="demo: zero SDK and transport retries" if bounded_demo() else "existing SDK defaults; provider retries unobserved",
        implementation_sha256=canonical_hash({str(path.relative_to(root)): sha256_text(path.read_text()) for path in files}),
        runtime="langgraph" if settings.LANGGRAPH_RUNTIME_ENABLED else "sequential",
        evidence_kind=settings.RESEARCH_EVIDENCE_KIND,
        fixture_sha256=settings.RESEARCH_FIXTURE_SHA256,
        dependencies=tuple((name, version(name)) for name in ("groq", "langgraph", "pydantic", "SQLAlchemy")),
    )


def deterministic_quality(task):
    if task.status.value not in {"completed", "failed"}:
        return None
    output = task.output or ""
    checks = []
    for rule in task.research.benchmark.checks:
        passed = False
        if task.status.value == "completed" and output.strip():
            folded = output.casefold()
            if rule.kind == "contains":
                passed = all(value.casefold() in folded for value in rule.values)
            elif rule.kind == "excludes":
                passed = all(value.casefold() not in folded for value in rule.values)
            elif rule.kind == "exact":
                passed = folded.strip() in [value.casefold() for value in rule.values]
            elif rule.kind == "json_fields":
                try:
                    parsed = json.loads(output)
                    expected = {key: json.loads(value) for key, value in (entry.split("=", 1) for entry in rule.values)}
                    passed = isinstance(parsed, dict) and set(parsed) == set(expected) and all(
                        type(parsed[key]) in (int, float) and parsed[key] == value for key, value in expected.items())
                except (ValueError, TypeError):
                    passed = False
        checks.append({"id": rule.id, "description": rule.description, "passed": passed})
    return {"version": "deterministic-v1", "score": sum(c["passed"] for c in checks) / len(checks), "checks": checks,
            "limitations": "Equal-weight surface checks; matching facts does not establish semantic correctness or faithful reasoning."}


def measured_usage(stages, field):
    started = [s for s in stages if s.started_at is not None]
    measured = [getattr(s, field) for s in started if getattr(s, field) is not None]
    coverage = "unavailable" if not measured else "complete" if len(measured) == len(started) else "partial"
    return {"coverage": coverage, "value": sum(measured) if coverage == "complete" else None,
            "measuredStages": len(measured), "startedStages": len(started)}


def run_metrics(task):
    started_events = [e for e in task.events if e.type == "agent_started"]
    start_counts = Counter(e.agent_id for e in started_events)
    timeout_evidence = any("timeout" in (e.type + " " + e.text).casefold() or "timed out" in e.text.casefold() for e in task.events)
    timeout_evidence |= any("timeout" in (s.error or "").casefold() or "timed out" in (s.error or "").casefold() for s in task.stages)
    digest = sha256_text(task.output) if task.output is not None else None
    matching_reviews = [r for r in task.human_reviews if r.assessment.expected_output_sha256 == digest]
    review = matching_reviews[-1] if matching_reviews else None
    human = statistics.mean(getattr(review.assessment, d) for d in DIMENSIONS) if review else None
    repeated = sum(max(0, count - 1) for count in start_counts.values())
    usage = {field: measured_usage(task.stages, field) for field in ("input_tokens", "output_tokens", "total_tokens")}
    if repeated:
        # Stage aggregates cannot prove usage coverage for each resumed attempt.
        for measured in usage.values():
            measured["coverage"] = "partial" if measured["measuredStages"] else "unavailable"
            measured["value"] = None
    return {
        "taskId": task.id, "mode": task.execution_mode.value, "benchmarkId": task.research.benchmark.id,
        "trialNumber": task.research.trial_number, "status": task.status.value, "error": task.error,
        "elapsedSeconds": task.elapsed_seconds, "stageTimings": [{"agentId": s.agent_id, "status": s.status, "seconds": s.duration_seconds} for s in task.stages],
        "agentCalls": len(started_events) if started_events else task.agent_invocation_count,
        "callMeasurement": "stage starts; not proof of provider requests", "handoffs": task.handoff_count,
        "completedAgents": [s.agent_id for s in task.stages if s.status == "completed"],
        "failedStages": [s.agent_id for s in task.stages if s.status == "failed"],
        "notExecutedAgents": [s.agent_id for s in task.stages if s.started_at is None],
        "selectedAgents": list(task.route_plan.selected_agent_ids) if task.route_plan else None,
        "skippedAgents": list(task.route_plan.skipped_agent_ids) if task.route_plan else None,
        "routeLength": len(task.route_plan.selected_agent_ids) if task.route_plan else None,
        "inputTokens": usage["input_tokens"], "outputTokens": usage["output_tokens"],
        "totalTokens": usage["total_tokens"], "timeoutObserved": timeout_evidence,
        "timeoutClassification": "explicit retained evidence only; sanitized provider errors may conceal timeouts",
        "repeatedStageStarts": repeated,
        "failedAttemptEvents": sum(e.type == "agent_failed" for e in task.events),
        "recoveryObserved": any("Server restarted" in e.text for e in task.events),
        "providerRetries": None, "cost": None, "outputSha256": digest,
        "deterministicQuality": deterministic_quality(task), "humanScore": human,
        "humanReview": review.model_dump(mode="json") if review else None,
        "modelAssisted": task.evaluation.quality.model_dump(mode="json") if task.evaluation and task.evaluation.quality else None,
    }


def describe(values):
    values = [v for v in values if v is not None and math.isfinite(v)]
    return {"n": len(values), "mean": statistics.mean(values) if values else None,
            "median": statistics.median(values) if values else None, "min": min(values) if values else None,
            "max": max(values) if values else None, "sampleStdDev": statistics.stdev(values) if len(values) > 1 else None}


def comparison(tasks):
    if not tasks:
        raise ValueError("No research runs")
    seed = tasks[0]
    metadata = seed.research
    integrity = []
    if any(t.research.experiment != metadata.experiment or t.research.configuration != metadata.configuration or t.research.run_ids != metadata.run_ids for t in tasks):
        integrity.append("Experiment configuration differs between recorded trials")
    if set(metadata.run_ids) != {t.id for t in tasks}:
        integrity.append("Some run evidence is missing or deleted")
    for task in tasks:
        if task.research.benchmark_sha256 != canonical_hash(task.research.benchmark.model_dump(mode="json")):
            integrity.append(f"Benchmark snapshot checksum mismatch for {task.id}")
        if task.directive != task.research.benchmark.execution_directive:
            integrity.append(f"Directive differs from benchmark snapshot for {task.id}")
        # Agreement between hashes is insufficient if every hash is missing or
        # identically corrupt. Recompute from the retained benchmark source.
        expected_input = build_input_fingerprint(
            directive=task.research.benchmark.execution_directive,
            requested_task_type=task.research.benchmark.task_type,
            dataset_id=None, dataset_checksum=None, benchmark_context=None, uploads=(),
        )
        provenance = task.provenance
        if (provenance is None
                or provenance.input_fingerprint != expected_input
                or provenance.directive_sha256 != sha256_text(task.directive)
                or provenance.requested_task_type != task.research.benchmark.task_type
                or task.uploads or task.dataset_id is not None
                or task.dataset_checksum is not None or task.benchmark_context is not None):
            integrity.append(f"Input provenance missing or inconsistent for {task.id}")
        configured_models = dict(task.research.configuration.agent_models)
        if any(stage.model is not None and stage.model != configured_models.get(stage.agent_id) for stage in task.stages):
            integrity.append(f"Observed stage model differs from configuration for {task.id}")
    identities = [(t.research.benchmark.id, t.execution_mode.value, t.research.trial_number) for t in tasks]
    if len(set(identities)) != len(identities):
        integrity.append("Duplicate benchmark/mode/trial identity")
    runs = [run_metrics(t) for t in tasks]
    cells = []
    for bid in metadata.experiment.benchmark_ids:
        case_tasks = [t for t in tasks if t.research.benchmark.id == bid]
        if len({t.provenance.input_fingerprint for t in case_tasks if t.provenance}) > 1 or len({t.research.benchmark_sha256 for t in case_tasks}) > 1:
            integrity.append(f"Input or benchmark mismatch for {bid}")
        for mode in metadata.experiment.modes:
            group = [r for r in runs if r["benchmarkId"] == bid and r["mode"] == mode]
            terminal = [r for r in group if r["status"] in {"completed", "failed"}]
            routes = Counter(tuple(r["selectedAgents"]) for r in group if r["selectedAgents"] is not None)
            cells.append({"benchmarkId": bid, "mode": mode, "expectedTrials": metadata.experiment.repetitions,
                          "recordedTrials": len(group), "terminalTrials": len(terminal), "successRate": sum(r["status"] == "completed" for r in terminal) / len(terminal) if terminal else None,
                          "failureRate": sum(r["status"] == "failed" for r in terminal) / len(terminal) if terminal else None,
                          "observedTimeoutRate": sum(r["timeoutObserved"] for r in terminal) / len(terminal) if terminal else None,
                          "latency": describe([r["elapsedSeconds"] for r in terminal]),
                          "agentCalls": describe([r["agentCalls"] for r in terminal]), "handoffs": describe([r["handoffs"] for r in terminal]),
                          "completedAgentCount": describe([len(r["completedAgents"]) for r in terminal]),
                          "skippedAgentCount": describe([len(r["skippedAgents"]) if r["skippedAgents"] is not None else None for r in terminal]),
                          "tokens": describe([r["totalTokens"]["value"] for r in terminal]),
                          "deterministicQuality": describe([r["deterministicQuality"]["score"] for r in terminal]),
                          "humanQuality": describe([r["humanScore"] for r in terminal]),
                          "routeVariants": [{"agents": list(route), "count": count} for route, count in sorted(routes.items())],
                          "routeConsistency": max(routes.values()) / sum(routes.values()) if routes else None})
    return {"experimentId": seed.experiment_id, "createdAt": min(t.created_at or t.started_at for t in tasks).isoformat(),
            "experiment": metadata.experiment.model_dump(mode="json"), "configuration": metadata.configuration.model_dump(mode="json"),
            "parentExperimentId": metadata.parent_experiment_id, "integrityIssues": integrity, "comparable": not integrity,
            "runs": runs, "cells": cells, "status": "complete" if len(runs) == len(metadata.run_ids) and all(r["status"] in {"completed", "failed"} for r in runs) else "incomplete",
            "statisticalScope": "Descriptive only; 1-5 trials per case/mode. No significance test or global winner.",
            "limitations": ["Deterministic fixture evidence validates machinery, not model quality, speed or pricing.", "Missing usage stays unknown; complete-coverage runs alone enter token statistics.", "Latency includes execution/persistence overhead, excludes queue wait; stage timing accumulates observed retries.", "Source checks can pass incorrect reasoning; use human review.", "SDK retries and sanitized timeout causes are not fully observable; cost is unavailable.", "Configuration reproducibility does not guarantee identical provider output."]}


def report(tasks):
    summary = comparison(tasks)
    evidence = [{"task": t.model_dump(mode="json"), "metrics": run_metrics(t)} for t in tasks]
    return {"reportVersion": "research-report-v1", "observedEvidence": summary, "runEvidence": evidence,
            "interpretation": "Compare each benchmark separately. Fewer selected stages establishes avoidance, not that the avoided reasoning was unnecessary. Review quality and failures before interpreting efficiency.",
            "researchConclusion": "No live-provider comparative conclusion is established by fixture acceptance. No global superiority or statistical significance is inferred.",
            "reproduce": {"configuration": summary["configuration"], "request": summary["experiment"], "rerunPath": f"/api/v1/experiments/research/{summary['experimentId']}/rerun", "rubric": HUMAN_RUBRIC}}
