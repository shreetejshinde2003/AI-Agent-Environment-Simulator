# Phase 9 local acceptance

Validated 7 October 2026 (Asia/Kolkata). Phase 9 passes local deterministic-fixture
acceptance. Provider-live research and independent quality conclusions remain
outstanding gates. Phase 10 has not started and requires a separate instruction.

## Actual starting repository

Starting HEAD was `e9b42633de2a8f5caa4bba047abbc49a6b76fe66` on main.
`ff60b93`, `0904f79`, and `e9b4263` were the latest Phase 8 commits. Only untracked
AGENTS.md existed; it was read and never edited, staged, committed or deleted.
No other existing user changes were present. Phase 4–8 reports and their saved
acceptance evidence were inspected, along with matched-experiment APIs,
Single/Fixed/Adaptive workers and graphs, Task/StageExecution/RoutePlan,
metrics storage, central provider adapter, datasets, research UI and fixtures.
Phase 8's saved reports record 746 backend, 124 frontend and 27 manual browser
passes with no failures/skips. Final regression retains those tests.

Current repository schema is 13. The root `simulator.db` reports version 13.
An older `backend/simulator.db` reports version 9 and was left unchanged; it was
not an acceptance database. All Phase 9 acceptance uses isolated databases, and
existing migration compatibility tests remain included. No Phase 9 migration or
new table was required.

## Benchmark design and experiment framework

Seven version-1 synthetic cases cover direct answer, synthesis, structured data
reasoning, multistep analysis, summarization, report generation, and mixed route
selection. Their rationales, directives, source/context, supported modes and
checks are committed in `database/benchmarks/research-v1.json`. No private HR
records or real model answers are committed as benchmark input.

Experiment admission groups existing Tasks across chosen modes and 1–5 repeated
trials, capped at 45 runs. It prepares all routes first and commits admission
atomically. Existing enqueue/worker execution runs trials sequentially with
rotating mode order. Every Task preserves the case snapshot/checksum, complete
configuration, expected run IDs, trial number, versions and input fingerprint.
The central adapter pins recorded per-agent model and output-token settings.
Implementation/package/runtime/fixture drift rejects same-configuration rerun.
Reruns create new IDs with a parent link and preserve original records.

## Metrics and quality

Comparisons are derived from saved evidence, by benchmark and mode: run/stage
latency, recorded stage starts, handoffs, completed/failed/unstarted agents,
selected/skipped routes, route length/consistency, input/output/total usage,
success/failure rate, explicit timeout evidence, repeated starts and recovery.
Missing/partial usage remains unknown; real zero remains measured. SDK-internal
retries, concealed timeout causes and monetary cost remain unavailable.

Deterministic checks expose rule outcomes and the equal-weight pass fraction.
They are limited surface checks, not semantic ground truth. Human-v1 requires
seven scored dimensions plus rationale, retains append-only actor/time/source/
output-bound history, and rejects stale/conflicting writes. The latest applicable
review mean has explicit equal dimension weights. No efficiency/quality composite
or global leaderboard is introduced. Existing model-assisted judgments remain
non-authoritative, with versions/scores/rationales/limitations preserved. Research
judge invocation defaults disabled; none was invoked.

Every cell reports sample counts, mean, median, min/max and sample standard
deviation only when meaningful. All samples are labeled descriptive only;
no inferential statistics, significance or global superiority is claimed.

## Actual comparative evidence

The reproducible acceptance command executed the real API and execution engine
against disposable SQLite with the SDK boundary mocked, then exported all
original Tasks/stages/events/handoffs/provenance in
`acceptance/phase9-fixture-report.json`. The report matches the final execution
implementation digest. It contains seven cases × three modes × two repetitions:
42 completed fixture trials, with no failure in this success-fixture dataset.
Failure behavior is separately exercised in automated and browser acceptance.

The following is balanced-suite accounting, not a pooled model performance
ranking. Each mode executes the same seven cases twice.

| Mode | Trials | Recorded stage starts | Handoffs | Controlled fixture tokens |
| --- | ---: | ---: | ---: | ---: |
| Single | 14 | 14 | 0 | 252 |
| Fixed | 14 | 70 | 56 | 1260 |
| Adaptive | 14 | 32 | 18 | 576 |

Adaptive paths are Research→Report (direct/synthesis), Data→Analysis→Report
(data), Analysis→Report (analytical), Summarizer→Report (summary), Report alone
(report), and Data→Analysis→Summarizer→Report (mixed). Each repeated route is
consistent for the fixed input/configuration. Compared with Fixed, routing
avoids 1–4 specialists by case. This establishes recorded stage avoidance;
quality data is required to decide whether each skipped stage was unnecessary.

All 42 success-fixture outputs pass their deterministic rules because the
fixture deliberately supplies known responses. Each mocked completion reports
11 input and 7 output tokens. These are controlled test values, not real usage.
Task/stage timings are actual local timing measurements, including SQLite and
execution overhead, with no real provider/network latency. Per-case statistics
are retained in the report. No independent human assessment or judge score is
claimed for the research result set. The browser-only entered rubric score is
explicitly annotated as fixture UI acceptance, not independent research judgment.

**Observed evidence:** persistence, routing, call/handoff counting, timing capture,
usage coverage, deterministic rule handling, failure behavior and report derivation
work through the existing engine. **Interpretation:** this validates the evaluation
machinery and demonstrates differing execution topology. **Research conclusion:**
no globally superior mode, real quality gain, live latency advantage, pricing
advantage or statistical significance has been established.

## Frontend and security

Research Lab exposes registry cases, case/mode selection, repetition bounds,
admission, persisted history, per-case comparisons, route stability, individual
trial evidence, the existing inspector, human scoring, failed runs, rerun and
report export. Tables show measurement n, units and unavailable telemetry.
No placeholder chart or metric is used. Workspace switching clears old state,
aborts reads and discards stale responses. Creation acknowledgement uncertainty
requires reload before retry; actions use a synchronous admission lock.

The complete report preview was added after the in-app browser failed to emit
file-download events for the JSON blob. Export API content and selection/copy
preview are verified; a saved browser download is not claimed.

Research roots and all evidence reuse current simulation IAM/tenancy and inherited
PostgreSQL ENABLE/FORCE RLS. Cross-tenant list/detail/export/rerun/scoring fail closed.
SQLite IAM checks protect admission, reads, scoring and worker evidence writes;
revocation stops a worker before invoking a provider. PostgreSQL tests execute
real grouped runs, append reviews, test immutable metadata/atomic rollback,
verify unscoped/foreign queries return no data, and test revoked membership.
Original Phase 4–8 RLS, graph/checkpoint/recovery and HR regressions remain green.

## Validation and cleanup

| Validation | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Full backend regression, including approved real local PostgreSQL/checkpoint cases | 795 | 0 | 0 |
| Full frontend regression | 135 | 0 | 0 |
| Manual browser checkpoints | 20 | 0 remaining | 0 |
| Exported success-fixture research trials (not automated test count) | 42 | 0 | 0 |

Logs: `acceptance/phase9-backend-validation.txt`,
`phase9-frontend-validation.txt`, `phase9-focused-validation.txt`,
`phase9-browser-checklist.md`, `phase9-lint.txt`, `phase9-build.txt`, and
`phase9-database-cleanup.txt`. Python compilation, pip dependency consistency and
Git whitespace checks pass. Two existing backend dependency deprecations and
two existing frontend Fast Refresh lint warnings remain. The production frontend
build succeeds with its bundle-size advisory. Existing React Flow development
warnings were seen while using the inspector; they did not prevent saved
run inspection. No new lint warning remains in Research Lab.

An early full run found two PostgreSQL race-test failures because the temporary
role ceiling was two connections while those tests require three. The ceiling was
corrected and the tests passed. The immutable-evidence guard adds a second locked
payload read during recovery; the existing test's exact count was updated while
preserving its tenant-scope and lock assertions. The final 795-test run includes
all corrections and the final backend implementation.

The user explicitly approved temporary local PostgreSQL access. Restricted
NOSUPERUSER/NOBYPASSRLS roles were used on fm_tenant_test at 127.0.0.1:55432,
with random application test schemas and a dedicated phase9_checkpoints schema.
Credentials lived only in a mode-0600 private password file under a mode-0700
temporary directory. Both login roles are now NOLOGIN with NULL passwords;
CONNECT/CREATE grants were revoked. The checkpoint schema and its temporary
owner role were removed. Verification reports zero sessions, zero role-owned
application schemas and zero checkpoint schema. Credential/setup/browser/failure
scripts, disposable browser database and private directory were removed. Both
acceptance servers were stopped, with no listeners remaining on 8019 or 5179.

## Git and remaining gates

Batch A local commit: `c2cd390` — versioned benchmarks/evaluation contracts.
Batch B local commit: `97a2c68` — persisted tenant experiments/comparison APIs.
Batch C is the Research Lab and acceptance commit containing this report.
Only Phase 9 files are staged/committed; AGENTS.md remains the intentionally
untracked file. There was no push, deployment, Railway change, production graph
activation, credential exposure, live provider request or Phase 10 work.

Phase 9 is locally complete under the requested fixture-only acceptance policy.
Actual research needs separately approved live repeated execution and independent
quality assessment. Configuration reproduction is supported; identical provider
text is not guaranteed. Phase 10 can be authorized separately and does not begin
as part of this task.
