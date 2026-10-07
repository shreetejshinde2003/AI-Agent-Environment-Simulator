# Phase 9 research and evaluation

Phase 9 extends the existing execution platform. Task remains the run lifecycle,
StageExecution remains stage evidence, RoutePlan remains Adaptive routing, and
simulation_metrics remains existing telemetry persistence. There is no new
execution engine, result table, migration, provider client, or schema version.
The schema remains 13. Research metadata and append-only human assessments are
stored in the existing tenant-owned Task JSON payload, on SQLite and PostgreSQL.

## Benchmark design

The safe synthetic suite is `database/benchmarks/research-v1.json`. Every case has
an ID, version, rationale, directive, source, expected task type, applicable modes,
and explicit checks. Source text is appended with the existing Source delimiter;
all treatments receive exactly the same directive and source. Private HR datasets
are not needed and no individual employment decisions are benchmarked.

| Case | Purpose | Deterministic criteria |
| --- | --- | --- |
| B-direct | Bounded glossary answer; test the direct baseline | Exact expansion of RTO |
| B-synthesis | Combine two independent source notes | All six owner/team/month facts |
| B-data | Structured data reasoning | Strict JSON, correct numeric total and average |
| B-analytical | Chained annual-cost comparison | Both costs, savings and selected plan |
| B-summary | Retain critical update facts during compression | Date, risk and mitigation |
| B-report | Organize a grounded report | Required section labels and source facts |
| B-mixed | Extract, analyze dependencies and summarize | Section labels and every action owner |

Substring checks are intentionally surface checks, not semantic correctness.
They can miss valid paraphrases, accept misleading surrounding text, and do not
fully check formatting, sentence limits, citations or reasoning. A passing
check is not sufficient to establish output quality. Exact and JSON checks are
stricter. Failed terminal runs score zero; pending runs have no quality score.
Checks have equal weight within each case, with the passed fraction exposed.
No efficiency/quality composite or cross-case weighted leaderboard is used.

Benchmark models are frozen. Admission stores the full case snapshot and its
canonical SHA-256 in every trial. Existing snapshots cannot be replaced by a
later registry edit. Published benchmark changes require a new version/protocol;
do not redefine version 1 in an established experiment set. Rerun fails on
registry, implementation, runtime, dependency, fixture or model drift. A new
configuration requires a new experiment rather than silently changing treatment.

## Experiment grouping and reproducibility

The authenticated `/api/v1/experiments` API adds:

- `GET /benchmarks`: versioned suite, rubric, server configuration and execution gate.
- `POST /research`: atomic grouped admission, then the existing enqueue/worker path.
- `GET /research`: workspace experiment history.
- `GET /research/{id}`: derived case/mode descriptive summaries and individual trials.
- `POST /research/{id}/rerun`: same logical configuration, new IDs, parent experiment link.
- `POST /research/{id}/runs/{task_id}/human-review`: attributed, output-bound assessment.
- `GET /research/{id}/report`: exportable JSON with original run evidence.

Choose unique cases and modes, 1–5 repetitions, and at most 45 runs. Trials run
sequentially using FastAPI BackgroundTasks; mode order rotates by repetition.
This bounds local resource use and avoids always placing Single first. It does
not remove all ordering, cache, system-load or provider temporal effects.
Every Task stores the complete experiment configuration, all expected run IDs,
case/version/checksum, trial number, rubric version and optional parent ID.
Existing RunProvenance stores the matching input fingerprint, prompt/contract
versions and requested task type. Existing stages store observed model/usage.

Configuration records the provider, per-agent models, output token ceiling,
execution implementation digest, relevant package versions, runtime, evidence
kind, and fixture digest when applicable. All six active research agents currently
resolve to the same configured default model; the configured fast-model setting
is not used by their current process methods. Stage calls are pinned to recorded
model/token settings through the existing central adapter. Workers stop before
a provider call if configuration or the execution gate changes. Workspace IAM
is rechecked during each research evidence write, before invocation and before
accepting output. Revoked principals cannot persist a successful result.

Preparation happens before persistence. Group admission is one tenant transaction;
a failed admission rolls back every Task. Existing enqueue and recovery semantics
remain authoritative. Missing/deleted trials are reported as incomplete evidence,
with comparison blocked. Registry/directive/checksum, configuration, trial identity,
input-fingerprint and observed-model inconsistencies also block comparability.
Original runs and reviews are not copied into a rerun.

Provider sampling parameters and seed are not exposed by the existing adapter.
Provider-default sampling is recorded. This supports configuration reproduction,
not identical LLM text. No output-determinism guarantee is made.

## Measures and statistical treatment

Efficiency: Task.elapsed_seconds (execution/persistence overhead, queue wait
excluded), each stage's accumulated duration, recorded stage starts, persisted
handoffs, completed stages, failed stages, unstarted selected stages, and input,
output and total tokens. Stage starts are not proof a provider request reached
the service. Adaptive selected/skipped agents and route length are derived only
from RoutePlan; Fixed/Single routing measures remain not applicable.

Token coverage distinguishes complete, partial and unavailable, including real
zero. Partial totals are not imputed or included in token statistics. Repeated
stage starts make usage partial because aggregate StageExecution fields cannot
prove coverage for every resumed attempt. Provider-internal retries are unknown.
No token-count estimate, pricing estimate or monetary cost is fabricated.

Reliability: latest terminal success/failure rates, failed-stage identities,
failed-attempt events, repeated starts, startup-recovery evidence and explicit
retained timeout evidence. Sanitized provider diagnostics may conceal timeout
causes, so observed timeout rate is a lower-bound observation, not a complete
provider timeout rate. Existing durable graph recovery/resume tests remain part
of regression. Production graph runtime stays disabled.

Each case/mode cell shows sample count, mean, median, min/max and sample standard
deviation (only n >= 2). Success rates use terminal runs and expose terminal,
recorded and expected counts. Pending runs are excluded. No significance test,
confidence interval, superiority test, global winner or pooled cross-case ranking
is generated. All 1–5 trial results are labeled descriptive only. Adaptive route
variants and modal-route frequency expose routing consistency across repetitions.
Avoidance counts establish skipped work, not that the avoided reasoning was
unnecessary or that quality is equal.

## Layered quality evaluation

Deterministic-v1 exposes each rule outcome and the equal-weight pass fraction.
Human-v1 requires correctness, relevance, completeness, clarity, groundedness,
concision and source consistency, each integer 1–5 with a rationale. Anchors are
1 materially wrong/missing, 2 major weaknesses, 3 adequate with meaningful omissions,
4 strong with minor weaknesses, 5 fully meets the criterion. Groundedness evaluates
unsupported claims; source consistency evaluates contradictions. Concision evaluates
unnecessary verbosity. The equal-weight seven-dimension mean is explicitly
subjective and descriptive. Original scores, notes, reviewer and time are retained
append-only. The latest review matching the current output digest is used in the
cell; stale-output scores are excluded. Review-count/output-digest conflicts reject
stale writes rather than overwriting another review. Review history is bounded to
50 entries per run. A research panel should score blinded outputs independently
and report agreement before drawing quality conclusions; local fixture acceptance
does not provide such a panel.

The existing model-assisted evaluator remains separate and non-authoritative.
Its recorded provider/model, rubric/protocol/prompt versions, criterion scores,
rationales, output digest and limitations appear in reports when available.
No calibrated uncertainty estimate exists. `RESEARCH_JUDGE_ENABLED` defaults
false for Phase 9 runs. No judge was invoked during acceptance.

## Research Lab and report

Research Lab is a sidebar destination integrated with the existing workspace
selection and run inspector. It lists real cases, selects cases/modes/repetitions,
starts approved execution, polls pending summaries, compares per-case tables,
shows route stability/avoidance, opens existing evidence, accepts rubric entries,
inspects failures, reloads saved history and reruns unchanged configurations.
Missing data displays an explicit empty or Unknown state. No fake charts are
shown. Tables expose units, denominators and measurement counts. Switching
workspaces remounts state, aborts reads and discards stale mutation responses.
A synchronous action lock prevents repeated admission while a request is pending;
uncertain creation acknowledgement instructs the user to reload before retrying.

Reports separate `observedEvidence`, original `runEvidence`, `interpretation`,
`researchConclusion`, and `reproduce`. The report is downloadable JSON; a complete
read-only preview permits selection/copy when browser file saving is unavailable.
The in-app browser used for acceptance did not emit a file-download event, so
this preview path was implemented and verified. Successful export does not imply
a live research conclusion.

## Provider gate and local reproduction

`RESEARCH_LIVE_ENABLED` defaults false. Explicit approval is required before an
operator enables live research. `RESEARCH_EVIDENCE_KIND` defaults provider_live;
only acceptance tooling sets deterministic_fixture and its fixture digest.
The browser explains whether admission will invoke live or fixture execution.
Phase 9 does not toggle the existing generic simulation behavior, production
LangGraph setting, deployed environment, or any provider key.

From the repository root, reproduce the safe acceptance dataset with:

```sh
.venv/bin/python backend/scripts/research_acceptance.py
```

This replaces the SDK boundary before any admission, uses the real engine/API and
a disposable SQLite database, and exports 42 actual fixture trials to
`docs/acceptance/phase9-fixture-report.json`: seven cases × three modes × two trials.
IDs/timestamps/local execution timings will change. Fixture text and usage are
controlled values, not provider measurements. The disposable store is removed;
full original Task evidence remains in the exported report. Automated tests use
fixtures only. PostgreSQL enforcement tests require separately approved restricted
local credentials and isolated schemas as documented in earlier acceptance.

Provider-live execution, independent human evaluation, repeated live quality/
latency/usage measurements, and research conclusions are outstanding research
gates. No real model behavior or globally superior mode is established here.
