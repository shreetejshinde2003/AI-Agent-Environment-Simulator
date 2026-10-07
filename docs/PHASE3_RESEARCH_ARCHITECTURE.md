# Phase 3 research architecture

> Historical Phase 3 snapshot and design rationale. Current implementation is
> documented in [FINAL_PROJECT_GUIDE.md](FINAL_PROJECT_GUIDE.md), including installed
> but gated LangGraph, authentication, HR/HITL and Research Lab. Statements below
> about unavailable evaluation/auth/graphs describe that earlier phase, not Phase 10.

Status: Phase 3.1 **COMPLETED** and production-verified at `8f0a489`.
Phase 3.2 contracts are **COMPLETED**, production-verified at `2c80606` as reported
by the project team. Phase 3.3 rule-based Adaptive execution and focused run UX
are **COMPLETED locally**; their production rollout remains **PARTIAL**.
Formal evaluation and LLM-based routing are **NOT IMPLEMENTED**.

Phase 3.1 uses one `executionMode` field: `single` (neutral Direct Agent),
`fixed` (the unchanged five-stage sequence), or `adaptive` (now operational with
the deterministic `rules-v1` planner). Legacy `full_pipeline` inputs and snapshots normalize to `fixed`;
legacy `single_agent` remains a separate individual-specialist compatibility
action, never a research baseline. Existing v2 string/JSON storage accepts these
values without a schema migration. The mode is persisted and included in task
responses, run events and metric history. Adaptive route plans now exist; scores
remain unset. The later research/evaluation sections below are a design, not
claims of completed experiments. The Phase 3.3 implementation section supersedes
earlier prospective planner/UI wording.

## 1. Current architecture: code-level findings

| Concern | Current implementation | Phase 3 implication |
|---|---|---|
| Creation/mode | `backend/app/api/routes/tasks.py:create_task` handles `/tasks`; `/simulations` delegates to it. `executionMode` accepts `single`, `fixed`, `adaptive` and legacy `single_agent`; legacy `full_pipeline` maps to `fixed`. The UI defaults to fixed. | Existing `single_agent` means one selected specialist, **not** a controlled direct-answer baseline. |
| Execution | `_run_task` uses FastAPI `BackgroundTasks`; `_run_pipeline` loops over the fixed five-stage tuple; `_run_stage` calls `agent.run(directive, context)` and stops on failure. | Reuse this lifecycle and stage executor with a validated plan; do not create three disconnected engines. One worker remains a constraint. |
| Prompt/handoff | `ExecutionContext` carries the original directive, bounded reference context and real prior outputs with producer IDs. `contracts.py` binds each specialist to its preferred available artifact. | Fixed exact handoffs are preserved; Adaptive now uses supported alternatives without inventing skipped outputs. |
| Measurements | `BaseAgent.run` and `llm_client.call_llm` capture model/usage; a request-local `ContextVar` writes tokens/model into `StageExecution`. `_run_stage` measures stage duration; `_run_task` measures wall time. `simulations.py` aggregates persisted runs. | Separate stage attempts from confirmed provider calls. `call_llm` currently substitutes zero when a successful response has no usage block; treat that as unknown before a formal token comparison. `call_llm` passes no temperature/seed, so repeatability is not controlled yet. |
| Persistence/events | `storage/database.py` transactionally saves a compatible Task JSON snapshot plus v2 relational projections. `storage/models.py` has simulations, tasks, stages, messages, events, metrics, uploads and dataset registry. `emit`, `record_message`, `record_activity` persist before `manager.broadcast`; `/ws/live` sends `{event,data,timestamp}`. | Keep one authoritative run record and event stream; new experiment metadata needs versioned storage, not a second hidden store. REST remains authoritative after reconnect. |
| Graph/UI | `AgentRelationshipGraph.jsx` uses persisted stages; the no-task preview still shows the fixed path. Task details/history label the stored mode. | Adaptive now renders only selected stages and a separate routing trace; new-run selection and readable run picker are implemented. |
| Datasets | `dataset_id`, checksum, `task_type` and bounded aggregate `benchmark_context` are attached at creation. `datasets/registry.py` validates six Git-ignored JSON inputs and excludes individual/protected fields from agent context. | Current HR experiments are aggregate-level. Raw-row extraction, full-dataset reasoning and context-size experiments are **not** supported by this bounded context. Production provisioning of the six files is **PARTIAL**. |

`agents/orchestrator.py` is an inactive LangGraph prototype, not the execution
path; `web_search_agent.py` is unavailable. Neither should be activated by this
design. The current graph is a visualization, not evidence of LangGraph runtime.

## Phase 3.2: shared context and specialist contracts

Before Phase 3.2, Research and Direct used the directive plus optional prepared
uploads/benchmark aggregates. Data appended `research_findings` even when empty;
Analysis did the same for `structured_data`, Summarizer for `insights`, and Report
for `summary`. Those last three ignored alternative upstream artifacts. All five
specialists could previously run from a directive alone, but an empty upstream
section could invite an unsupported answer. The new contracts are:

| Agent | Capability; output | Required input | Optional input; preferred artifact | Missing-input behavior |
|---|---|---|---|---|
| Research | knowledge research; `research_findings` | Original directive | Prepared upload, safe benchmark aggregates, internal source text | Works from directive; no browsing claim. |
| Data | structure/extract; `structured_data` | Original directive | `research_findings`, prepared upload, benchmark aggregates, source text; prefer findings | Works from facts in directive or supplied data; does not invent findings. |
| Analysis | analyze/compare/reason; `insights` | Original directive | `structured_data`, `research_findings`, prepared upload, benchmark aggregates, source text; prefer structured data, then findings | May reason from directive; states evidence limits when needed. |
| Summarizer | summarize; `summary` | Original directive **and one actual source** | `insights`, `structured_data`, `research_findings`, prepared upload, benchmark aggregates, source text; prefer in that order | Adaptive context without a source fails before a model call. Legacy individual-specialist mode still permits source material embedded in its directive. |
| Report | report/synthesize; `final_report` | Original directive | `summary`, `insights`, `structured_data`, `research_findings`, prepared upload, benchmark aggregates, source text; prefer in that order | May answer from directive when evidence permits; cannot claim skipped work. |
| Direct baseline | direct answer; `final_answer` | Original directive | Prepared upload, benchmark aggregates | Remains a single model invocation; never calls specialists. |

`backend/app/agents/execution_context.py` defines a frozen, validated internal
`ExecutionContext`: original directive, mode, optional task type, bounded upload
and benchmark text, optional internal source text, ordered `AgentOutput` entries,
and optional `RouteSelection` metadata. Available and missing inputs are derived
from actual values. Successful coordinator output is appended with its producer
ID and exact text; absent stages produce no artifact. The strict legacy-dict
adapter supports existing Python agent callers but rejects unknown, blank,
oversized or malformed values. Normal task execution uses the typed form.

`backend/app/agents/contracts.py` is a small immutable registry of capabilities,
required inputs, optional alternatives, output names and predecessor preference.
It performs **input binding, not route selection**. For fixed mode, Data still
prefers Research, Analysis prefers Data, Summarizer prefers Analysis, and Report
prefers Summarizer. Raw uploaded text remains available in the typed context;
when an immediate artifact exists, Analysis/Summarizer/Report keep their former
prompt focus on that artifact plus benchmark aggregates. Missing optional
sections are omitted rather than rendered as empty upstream work.

Missing required material raises `AgentInputError` with safe code, agent ID and
missing input names. The task/stage snapshots persist this detail in optional
`inputError` fields alongside the existing failure status and message. No SQL
schema migration was needed; old snapshots load with null `inputError`. The
optional `RouteSelection` distinguishes selected from skipped agents, while
actual stage rows identify executed/failed work. Phase 3.3 derives it from the
persisted `RoutePlan`; fixed/single runs still create no skipped rows.
Validated examples such as Data → Analysis → Report, Research → Analysis →
Report, and Summarizer → Report are **structurally ready** when their required
source exists. Phase 3.3 adds a validated plan and reuses the stage runner;
`adaptive` no longer returns the not-implemented response.

## Phase 3.3 implementation: deterministic Adaptive and run UX

### Audit findings and execution boundary

`tasks.py` already centralizes creation, bounded context preparation, stage
execution, failure handling, persistence and WebSocket broadcasts. Fixed's five
tuples remain unchanged; `_run_sequence` is the shared actual-output/handoff loop
for Fixed and Adaptive. Single and legacy specialists retain `_run_stage`.
No agent prompts, provider settings or deployment architecture changed.

`routing.py` is a pure, versioned planner. It inspects normalized directive
instructions, explicit task category, attachment formats and benchmark presence.
Uploaded prose is not searched for routing instructions. Inline source material
is recognized only after a line-start `Source:`/`Text:` delimiter and excluded
from keyword inference. It remains the same original directive for all modes.

### Taxonomy and deterministic rules (`rules-v1`)

| Category | Required capabilities, in addition to final `report` |
|---|---|
| `summarization` | summarize |
| `transformation` | structure (Data also declares extract) |
| `analysis` | analyze (Analysis also declares compare/reason) |
| `structured_data_analysis` | structure + analyze |
| `research_synthesis` | knowledge_research; no browsing |
| `reporting` | final report only |
| `mixed` | union of detected requirements; if none, analyze + summarize |

An explicit documented `taskType` overrides inferred intent; unknown adaptive
types return 422. Otherwise whole-word signal groups detect summary/compression,
extraction/transformation, analysis/comparison/reasoning, and research/explanation.
Multiple groups produce `mixed`. CSV/JSON attachments or benchmark aggregates
add structure to analysis; absent intent signals they default to structured-data
analysis. Without structured data, report/draft/write defaults to reporting;
other unknown requests default to research synthesis. These fallbacks are
recorded category decisions, not a fallback to Fixed. A pure supplied-material
summary selects Summarizer → Report without Data just because the source is JSON.

Required capabilities select their providers from the existing contract registry,
in Research/Data/Analysis/Summarizer/Report dependency order. Report is always
selected for final presentation. This constructs ordered subsets, not a lookup
table of three canned routes. For example Analysis → Report, Data → Report,
Research → Summarizer → Report, and Report alone are possible. No Direct or
Web Search route is allowed. Rules are English keyword heuristics, not semantic
understanding, learned routing, or autonomous planning. Negation, indirect goals,
and multilingual requests can be misclassified; explicit categories provide a
documented override, not proof of routing accuracy.

### Plan, validation and truthful state

The frozen camelCase `RoutePlan` records `routerVersion`, `executionMode`,
`taskType`, `selectedAgentIds`, `skippedAgentIds`, `requiredCapabilities`,
`availableInputs`, `reasons`, `validationStatus`, and `validationError`.
The enclosing immutable simulation ID identifies the run/plan; no second plan
database is needed. Available input names come from prepared, validated context.
Reasons are short system rule explanations, not hidden model chain-of-thought.

Validation tracks input/output **names only**, checking unique implemented
specialists, supported order, exact selected/skipped partition, final Report,
required capabilities and each contract's required/all-or-any source conditions.
It never fabricates placeholder artifact text. Missing Summarizer source with
no earlier producer is rejected before persistence/model execution using
`422 detail={code: invalid_route, message, routePlan}`. Unsupported explicit
categories return the same code/message without a plan. There is no automatic
repair or silent full-chain fallback. Execution revalidates the stored plan
and exact stage list before invoking agents; corruption fails truthfully.

Only selected specialists have stage rows: waiting means selected/not yet run;
active/completed/failed describe actual execution. Skipped IDs live only in the
plan and do not count as calls, tokens or progress. Real outputs enter immutable
`ExecutionContext.with_output` with producer IDs; neighbor handoffs carry those
exact outputs. The actual Report output becomes `task.output`. On failure,
downstream selected stages remain waiting; completed ones stay completed.

`route_planned` follows `simulation_created`, before execution. Existing
task_created/task_updated carry the complete plan; stage/message/activity and
terminal events keep their existing envelope and persistence-before-broadcast
behavior. Graph topology comes from backend stages; skipped agents appear only
in the trace, never as successful nodes. Adaptive has Goal → selected stages →
Result, with the non-LLM planner described in the trace rather than a fake stage.

### Persistence, metrics and compatibility

`Task.title` and optional `routePlan` use the existing version-2 JSON/JSONB run
snapshot; normalized stages/messages/events still hold actual execution state.
No migration or table change is necessary. Old records derive a title from the
directive and have no invented route. IDs and execution-mode semantics remain
unchanged, including legacy Individual Specialist as a non-research utility.
Existing JSON export includes the plan; TXT adds title; CSV remains real stages.

Task/API updates expose `agentInvocationCount` (started stage attempts, not
confirmed HTTP calls) and `handoffCount`. Metrics history also includes title,
task type, dataset ID, selected/skipped IDs and actual recorded model names.
Tokens/latency remain measured stage/run fields; skipped work adds nothing.
No cost estimates or quality scores are introduced. Experiment groups, repeat
numbers, evaluator provenance and comparative analysis remain future work.

### Simulation-run UX and benchmark path

The old modal awaited `refresh()`, but an already-busy refresh returned early;
selection could then be replaced by an older task list. Creation now immediately
accepts the actual server response into run state, selects its ID, and opens the
workspace, before refreshing. Merging retains acknowledged runs omitted by stale
responses and rejects snapshots with fewer recorded events. This assumes the
current no-delete API; a future deletion API needs explicit removal handling.

Titles are literal normalized directive excerpts (80 characters maximum), or an
optional user-supplied API title; no semantic/title model call. IDs remain in
details, picker secondary text, API and exports. The native disclosure-based run
picker supports search, newest-first ordering, mode/status/time labels, keyboard
selection/Escape and a scrollable list. Workspace subtitles are mode-aware.

Benchmark flow remains: private six JSON files → strict family/schema/prefix
validation → operational registry metadata → checksum-verified bounded aggregate
context at run creation → real agent inputs. The directory is now configurable
through server-only `BENCHMARK_DATA_DIR`, defaulting to `data/benchmark/`.
Both the existing registration CLI and context loader use it. No second registry,
raw-row ingestion or public registration API was introduced. Empty deployments
explain that an administrator must provision/register files; active options use
Employee/HR · Small/Medium/Large labels. Private production file provisioning is
still **PARTIAL**; see [exact setup steps](PHASE2_DATABASE_DEPLOYMENT.md#private-benchmark-provisioning--phase-33).

### Research/product references (reviewed 2026-09-29)

These are general patterns, not copied interfaces or implemented feature claims:

- [FutureAGI simulation overview](https://docs.futureagi.com/docs/simulation/):
  keep simulation runs and evaluation distinct; a saved trace is evidence, not
  an invented quality score. Search-indexed documentation was available; direct
  overview retrieval timed out during review.
- [LangWatch Scenario blackbox testing](https://scenario-docs.langwatch.ai/testing-guides/blackbox-testing/):
  inspect actual trajectories as well as final text; retain API-level integration
  tests separately from cheap deterministic unit tests.
- [Talkdesk Simulator](https://support.talkdesk.com/hc/en-us/articles/52487140094875-AI-Agent-Platform-Simulator):
  test orchestration before publishing and retain inspectable run identifiers.
  We expose concise rules and real handoffs, not private model reasoning.
- [OpenTrain agent simulations](https://www.opentrain.ai/solutions/agent-simulations/):
  scenario design and trajectory review are explicit research tasks. This is a
  service/talent reference, not a hidden execution backend; our team owns both.
- [UCP Tools simulator workflow](https://ucptools.dev/guides/fastucp): validate
  declared capabilities before exercising the actual path. Commerce is not scope.
- [Oracle HR agents](https://www.oracle.com/human-capital-management/human-resources/)
  and [Workforce Next HR/recruiting](https://wfnext.com/ai-agent-hr-recruiting/):
  illustrate domain-context/workflow integration, not a reason to copy recruiting
  automation. This project remains developer/research-facing. HR is an aggregate
  benchmark domain; individual hiring, rejection or employee ranking is excluded.

### Validation and remaining gates

Deterministic backend tests cover category/rule normalization, explicit overrides,
contract rejection, selected order, real artifact propagation, skipped zero calls,
failure stop/persistence, route reload, API/exports/events, real specialist prompt
binding with mocked provider responses, private-directory registry and protected
field exclusions. Existing Single/Fixed/legacy and SQLite/PostgreSQL-compatibility
tests remain. Frontend tests cover stale refresh merges, labels, actual topology
and dataset options/empty state. An isolated localhost browser smoke uses a
temporary database and conspicuously labeled mock outputs, never production data.

**PARTIAL:** production Adaptive verification, private benchmark provisioning,
scientific route accuracy/quality evidence. No live PostgreSQL or Groq call was
made for Phase 3.3; deterministic tests do not establish deployed integration or
answer quality. **NOT IMPLEMENTED:** LLM router, evaluation engine, adaptive
branching/replanning, LangGraph execution, auth, Web Search, pause/cancel, retries.
One worker/in-process BackgroundTasks and existing input limits remain.

## 2. Research question and three execution modes

Question: **On the same task and safe input, does selecting a smaller valid
agent path change answer quality, latency, token use, failure behavior or
interpretability relative to one direct LLM call and the existing fixed path?**
Treat these as hypotheses to test, not expected improvements.

| Research mode | Planned path | What is already available |
|---|---|---|
| Single baseline | Goal → one neutral direct-answer model call → Result | **COMPLETED** as `single`, using the Direct Agent and the same bounded uploaded/benchmark context as fixed mode. Legacy `single_agent` remains a specialist action, not this baseline. |
| Fixed | Goal → Research → Data → Analysis → Summarizer → Report → Result | **COMPLETED** as `fixed` (legacy input `full_pipeline` accepted); exact handoffs and failure semantics preserved. |
| Adaptive | Goal → explicit planner → selected valid specialist stages → Result | **COMPLETED locally** with `rules-v1`; planner is deterministic metadata, not an LLM stage. Production verification is **PARTIAL**. |

Shared conceptual interface: `plan(request) -> RoutePlan` then
`execute(plan, directive, prepared_input) -> persisted Task`. A plan should
carry mode, ordered stage IDs, each stage's required/produced artifact, selected
and skipped agents with reasons, router strategy/version, and a final-result
rule. One lifecycle emits queued/running/completed/failed, stage/activity/message
events, true progress (`completed selected stages / selected stages`), and the
same result/error shape. Only an executed agent produces a stage result; skipped
agents are plan decisions, not successful `StageExecution` rows. Keep the
original directive and identical allowed dataset/upload context across arms.

Phase 3.2 binds available alternative artifacts: Analysis → Report passes actual
`insights` without fabricating `summary`. Phase 3.3 validates required inputs
before execution and persists the selected/skipped decisions.

## 3. Adaptive routing choices and recommendation

| Router | Difficulty / determinism | Cost / reproducibility | Failure and academic value |
|---|---|---|---|
| Explicit rules over task features | Low; deterministic at a versioned rule set | Zero routing tokens; easy replay | Brittle on ambiguous wording. Honest label: **rule-based adaptive routing**, not “AI routing.” Strong baseline. |
| Capability tags + dependency validation | Low–medium; deterministic when tags are fixed | Zero routing tokens; auditable plan | Bad tags or missing artifact contracts cause invalid plans; useful for inspecting why agents were chosen. |
| LLM plan/classification | Medium–high; stochastic unless provider controls allow otherwise | Extra model call/tokens; record prompt/model/version | Can invent unavailable agents or invalid order; needs schema validation, bounded fallback and independent route labels. A genuine AI-router comparison, not a prerequisite for a working adaptive mode. |
| Hybrid: rules validate LLM proposal | Medium–high | Extra call when used; reproducibility depends on model | Constrains unsafe plans but combines two routing effects; evaluate separately from the rule-only arm. |

**Recommendation:** implement a small capability-tagged, deterministic router
first, with explicit dependency checks and recorded selection/skip reasons.
Predefine and version task-feature rules; do not give the router a hidden gold
task label during experiments. If time and quota permit, add an independently
named LLM-router variant later, using the same plan validator and runner. Never
market rule selection alone as an AI routing algorithm. Bound stage count to
1–5; exclude Web Search and custom roster-only agents.

## 4. Small task taxonomy

| Type | Required capability / plausible agents (not a final route) | Expected output / benchmark fit |
|---|---|---|
| Summarize supplied material | Compression and direct answer; Summarizer, Report | Faithful concise summary; safe uploaded text or aggregate benchmark context. |
| Extract/structure | Field extraction and formatting; Data, Report | Schema-conforming fields; use synthetic or approved non-personal uploads. The current benchmark aggregate cannot validate row-level extraction. |
| Compare/analyze | Structure, tradeoffs, interpretation; Data, Analysis, Report | Supported comparison with limitations; employee/hr aggregates may apply **within** a family, not as merged employee records. |
| Reason/explain | Relevant background and reasoning; Research, Analysis, Report | Answer with explicit uncertainty; typically no HR dataset. Research is not live browsing. |
| Mixed synthesis/report | Evidence handling, analysis, compression, presentation; several specialists | Report satisfying multiple stated requirements; approved aggregate/short document context if relevant. |

Use a handful of prewritten task cards with required facts/output constraints;
taxonomy labels describe cases for analysis, not automatic gold routes. A
transformation-only task can be added if a clear reference output is available.

## 5. Reproducible experiment protocol

Pilot: two task cards from each of four useful types (eight cards), across
single/fixed/rule-adaptive, one run per card/mode: 24 runs. Then repeat a
preselected three-card subset once in all three modes: nine more runs. At an
illustrative three specialist calls per adaptive path, that is about 99 model
calls (single 11, fixed 55, adaptive about 33), **not a quota guarantee**.
Do not run until an explicit budget gate and test-only mocks are in place.
This pilot is descriptive; a broader repeat set would be needed for strong
variance or significance claims.

Freeze task text, prepared input bytes/hash, reference answers/fact cards,
rubric, route labels, prompt templates, router version and model IDs before
execution. Pair all three modes on each card; interleave/randomize arm order to
reduce time/provider drift. Use the same model where possible: current five
agents all set `MODEL=None` and use the default. Record the actual returned
model, max-output limit and provider usage. A future shared LLM call control may
set temperature/seed **only if the provider supports them**; current code does
not, so do not claim deterministic sampling. Run failures remain failures;
predeclare whether a failed trio is excluded from quality comparison while
still included in reliability/cost accounting. No silent re-run or imputation.

Analyze small/medium/large as **nested scaling variants**, not disjoint test
splits. Because the current registry sends only capped aggregate counts/ranges,
size changes record counts and preparation work, but does not automatically
create a long-context experiment. Any future context-size experiment needs an
approved, non-personal input generator and separate validation. Production
benchmark trials wait until private dataset provisioning is verified.

## 6. Evaluation: measured, judged, and missing

| Metric | Definition and type | Paid model call? / limitation |
|---|---|---|
| Wall latency | `completed_at - execution_started_at`/persisted elapsed seconds; **objective system**. Report median and per-task paired differences. | No; network conditions vary. Stage durations do not necessarily sum to wall time. |
| Tokens/model calls | Provider-reported input/output tokens, summed over measured calls; **objective when usage exists**. Count started stages separately from confirmed provider requests. | No extra call; failed calls or absent usage may be unknown. Correct the current zero fallback before comparing modes. |
| Path and reliability | Selected stages from plan, executed stages with `started_at`, handoffs from messages, and failure rate = failed runs / attempted runs; **objective from persisted state**. | No; started stage is not proof that the provider was reached. |
| Task completeness | Predeclared required items satisfied / applicable items, with evidence spans; **human rubric** or deterministic match for exact-output cards. | No for human/deterministic; subjectivity and ambiguous requirements. |
| Format correctness | Binary pass/fail from parsing and validating the predeclared output schema; **deterministic** when a schema exists. | No; says nothing about semantic truth. |
| Factual support/hallucination | Human reviewers mark checkable output claims as supported, unsupported or contradicted by the supplied reference; report each count and checked-claim denominator, not a universal “truth score.” | No for human; source may be incomplete. No web access means external fact-checking is out of scope. |
| Relevance/readability | Blind reviewer rating against predeclared anchors (e.g., 1 = off-task, 3 = partially meets the goal, 5 = directly meets it); **human ordinal**. Record reviewer and disagreements. | No; subjective, should not be collapsed into objective accuracy. |
| Routing precision/recall | With an independently annotated required-agent set: `|selected ∩ reference| / |selected|` and `|selected ∩ reference| / |reference|`; **reference-dependent**. | No; multiple routes can be valid, empty denominators need a declared rule, and order validity is separate. |
| Unnecessary-agent rate | `|selected − agreed minimal valid set| / |selected|` if a minimal route is defensible; also report extra calls/tokens relative to another arm. **Reference-dependent**. | No extra call; omit the rate when multiple non-comparable minimal routes exist. Fewer agents do not imply higher quality. |
| Repeated-run stability | On the preselected repeat subset, report spread of completion, required-item coverage, latency and tokens across repeats; **descriptive**, not a universal semantic-similarity score. | No extra evaluator call; the limited repeat count gives weak precision. |

Do not add one opaque “overall score” by default. Plot quality against token
and time costs; use paired task-level comparisons and show raw values. An
optional LLM-as-judge must be explicitly labeled **model-rated**, store the
judge model/prompt/rubric, blind/shuffle outputs, and be checked against a
small human-rated subset. It adds paid calls and is not ground truth; published
work documents position/verbosity biases ([Zheng et al.](https://arxiv.org/abs/2306.05685)).
`Task.evaluation_scores` currently defaults to `None`; no actual evaluation
engine or score provenance exists.

## 7. Information-preservation study

This is feasible on a **small, controlled fact-card subset**, not arbitrary
open-ended answers. Before runs, define approved non-personal source facts and
which facts are required in the final answer. At every saved handoff/output,
human annotators mark each required fact as retained, altered, contradicted or
absent with a text span. Report a fact-retention fraction (retained required
facts / applicable required facts) and contradiction count at each stage,
including final output. A missing fact may be legitimate compression if it was
not required; annotate that before scoring. Compare final preservation across
modes; single has no internal handoff trajectory. This is an interpretable
manual protocol, **not** an implemented metric or a claim of novelty. Larger
automatic QA/NLI checks would need validation against human labels (for
example, [QAGS](https://aclanthology.org/2020.acl-main.450/) motivates factual
consistency checks but does not supply a ready-made project score).

## 8. Controlled failure/environment experiments

Future tests should inject failures at coordinator boundaries in a dedicated
test/experiment mode, not sabotage Groq or the production service. Safe cases:
malformed input rejected before run; missing required artifact; unavailable
agent; deterministic stage exception; configured deadline/timeout; exhausted
per-run token allowance; deliberately invalid route. A provider-error fixture
tests API-failure handling without a paid call. Real provider outages may be
observed but not intentionally induced. No retry/recovery policy is implemented;
“recovery outcome” is currently terminal failure and preserved evidence.

Persist requested injection, targeted stage, expected/actual failure type,
error (sanitized), event times, completed/failed/waiting stage states, and
whether any downstream call occurred. Separate synthetic failures from organic
ones in dashboards and analysis. A future timeout must distinguish local
deadline from provider-side timeout and should never imply a remote request was
cancelled if that cannot be confirmed.

## 9. Database and API implications

Existing v2 fields already cover `execution_mode`, `task_type`, `dataset_id` and
checksum; `agent_executions` covers ordered path, agent/model/status/latency/
tokens; messages/events cover handoffs/failure trace; `simulation_metrics`
covers measured totals. Dataset size is available in the registry but should be
snapshotted for a historical experiment, because registry metadata may change.
The JSON Task snapshot can hold a prototype plan, but its unstructured
`evaluation_scores` field is insufficient for provenance and comparisons.

**Minimum later versioned migration recommended:** one `experiment_runs` table
linked to simulation ID, with experiment group/case ID/run number, task type,
dataset ID/checksum/size snapshot, mode, planned route and decision reasons as
JSON, actual path derivable from stages, router/prompt versions, model settings,
input hash, optional failure-injection specification and failure taxonomy; and
one `evaluation_results` table keyed to a run/metric/evaluator/rubric version,
with value or category, evidence and optional reviewer identity code. Keep
stage-level model/tokens/latency in existing tables. No new table is necessary
solely for skipped agents if the immutable plan records them. A version 3
migration must preserve v2 rows and treat absent experiment metadata as null.
Do not add these tables until the experiment contract and rubric are agreed.

Phase 3.1 adds `single`/`fixed`/`adaptive` to the existing mode field, without
adding a database column or changing schema version 2. `/simulations` defaults
to fixed; legacy `/tasks` requests without a mode retain specialist behavior.
Future additive API should accept experiment identifiers without breaking
legacy specialist or fixed requests; expose the persisted execution plan,
selected/skipped reasons and per-run experimental metadata in simulation detail;
provide a paginated experiment comparison/read endpoint only after real data
exists. Reject invalid plans and unsupported agents with 4xx. Continue to use
existing `task_updated`, stage, handoff and simulation WebSocket events from
actual state transitions. No separate simulated event source.

## 10. Frontend implications

Offer clear labels: Direct-answer baseline, Fixed five-agent pipeline,
Rule-adaptive plan; keep “Individual specialist” as a distinct legacy action.
For a selected run, render Goal → actual stage(s) → Result in single mode;
Goal → Coordinator (non-LLM) → all five in fixed mode; and Goal
→ only selected stages → Result in adaptive mode (planner in the trace). Show skipped agents in a
separate explanation panel, never as completed nodes. Draw edges from the
validated plan and persisted handoff messages, not the static roster endpoint.
During execution, status comes from real stage rows; after reconnect, reload
REST. The timeline should include a persisted plan-created event and actual
stage/message transitions. Add mode/task/dataset filters and paired comparison
views only when runs/evaluations exist; otherwise show honest empty states.

Likely touch points later: `CreateTaskModal.jsx`, `AgentRelationshipGraph.jsx`,
`TaskDetailsPanel.jsx`, `MetricsCharts.jsx`, `SimulationContext.jsx`,
`useSimulationData.js`, and `apiClient.js`. The existing React Flow dependency
is sufficient; no new visualization framework is required.

## 11. LangGraph decision

| Criterion | Current FastAPI coordinator | Possible LangGraph runtime |
|---|---|---|
| Dynamic routing/branching | A validated ordered plan and loop are small to implement. | Conditional edges and shared state are first-class. |
| State/observability | Already persisted in Task/stage/message/event tables and broadcast through `/ws/live`. | Checkpoints/streaming could help, but would duplicate or require mapping to the existing schema/events. |
| Retries/checkpointing | Not implemented; active call cannot resume after restart. | Checkpoints at node boundaries can support durable continuation; re-executed nodes require idempotent side effects. |
| Complexity/risk | Preserves the verified fixed pipeline and current production behavior. | Adds dependency, migration, checkpoint storage and potential double-execution concerns. |
| Academic value | Comparisons depend on plans, outputs and evaluation, not framework branding. | Useful only if branching/loops/recovery become central research variables. |

**Decision A: keep custom orchestration for Phase 3.** Revisit an incremental
LangGraph prototype only if conditional loops, human interrupts or true durable
resumption are explicitly required and can be compared on the same contracts.
It is not active now. This tradeoff follows LangGraph's documented
[conditional-edge model](https://docs.langchain.com/oss/python/langgraph/graph-api)
and [checkpoint behavior](https://docs.langchain.com/oss/python/langgraph/graph-api#re-execution-and-idempotency),
not a claim that the current prototype provides those capabilities.

## 12. Benchmark role and production availability

Use the employee and hr families separately. They support descriptive analysis
of **approved aggregates**, routing decisions for data-bearing tasks, and
small/medium/large scaling of dataset preparation. They do not by themselves
provide ground-truth answer labels, independent train/test samples, or a valid
individual-employment decision task. Nested prefixes make independent-split
claims invalid. The current capped context also means input-token scaling must
be measured, not assumed from row counts. Never send Age, Gender, names, IDs,
manager links, individual salaries or performance ratings for individual
employment decisions.

Production file provisioning remains **PARTIAL**. A later approved option is a
private Railway volume holding only the six files at the backend's expected
`data/benchmark/` path, uploaded by the team after deployment, followed by
checksum validation and explicit registry registration. Alternatively, use a
private object store with a repository-owned loader; this is a larger change.
Do not commit raw files, expose a public download URL, or rely on Drive at
runtime. Verify the actual container path before choosing a mount; Railway
[documents runtime-mounted volumes](https://docs.railway.com/volumes), not
build-time availability. This design does not provision any service or volume.

## 13. Conservative academic contribution

Suggested report/abstract wording: “We built and evaluated a full-stack
multi-agent simulation platform that records real agent handoffs and execution
metrics, and we compare a direct-answer baseline, a fixed five-agent workflow,
and a capability-based adaptive workflow on controlled tasks. We analyze
quality–efficiency tradeoffs and information preservation across handoffs.”
Use “compare” only after the study is run; until then say “designed to compare.”
Do not claim a novel model, trained HR predictor, LangGraph runtime, or superiority
without measured evidence. The contribution is the integrated, inspectable
system and reproducible comparison protocol, not Groq, FastAPI, React Flow,
PostgreSQL or hosting platforms.

## 14. Ordered implementation checkpoints

| Checkpoint | Purpose and likely files | Dependency / tests / deliverable / risk / live calls |
|---|---|---|
| 3.1 Execution-mode foundation + direct baseline — **COMPLETED** | Canonical mode values, `_execute_mode` dispatch and neutral Direct Agent. | Mocked tests and production single/fixed runs with PostgreSQL restart persistence were verified at `8f0a489`. |
| 3.2 Typed context + specialist contracts — **COMPLETED** | Validated context, artifact provenance and small capability registry. | Production-regression verified at `2c80606` per team report. |
| 3.3 Rule-adaptive execution + run UX — **COMPLETED locally** | Capability planner/validator, persisted route, actual selected graph, run picker and private benchmark directory. | Mocked provider/backend tests, frontend tests/build/lint and isolated browser smoke. No Groq calls. Production rollout **PARTIAL**. |
| 3.4 Experiment identity/storage — future | Add experiment groups/repeats/input hashes only after agreeing the protocol. | 3.3. Safe additive migration if needed; preserve old snapshots. **Groq: no.** |
| 3.5 Experiment protocol preparation — future | Freeze task cards, route annotations, dataset inputs and bounded quota plan. | 3.4. Deterministic fixture/metadata checks; no invented metrics. **Groq: no.** |
| 3.6 Evaluation protocol/store | Predeclare task cards, fact references and rubric; implement metric capture/evaluation records and comparison API. | 3.3–3.5. Golden-fixture and blinded-human workflow tests; deliver no fabricated scores. Risk: subjective labels. **Groq: not for unit tests; pilot later.** |
| 3.7 Failure experiments | Gated deterministic injection and labeled outcomes. | 3.4, 3.6. Mock failures at every boundary; deliver reliable failure evidence without retries. Risk: accidental production exposure. **Groq: no by default.** |
| 3.8 Comparative dashboard/pilot | Paired mode views and bounded approved live experiment. | All prior gates. End-to-end checks, then explicit quota-limited runs; deliver raw results and limitations. Risk: API budget/provider drift. **Groq: yes, with approval/budget cap.** |

Review and commit checkpoints separately. Preserve the working fixed path as a
regression test throughout.

## 15. Quota and research risks

Unit, contract, migration, router, graph, failure and evaluator-format tests
must use mocked agents or recorded **test fixtures**, never live Groq. A minimal
real smoke test is needed only when the direct baseline/router integration is
ready; repeated live calls belong to a separately triggered experiment command
with a dry-run plan, expected maximum calls/tokens, explicit confirmation and
persisted run IDs. Do not run experiments at server startup or as part of CI.
Stop a batch on quota/provider errors; preserve partial results without
inventing scores. Never log credentials or raw protected HR records.

Primary limitations: small task set; prompt/model drift; provider randomness
without controlled temperature; lack of gold labels for open answers; subjective
route and quality judgments; overlapping dataset variants; bounded aggregate
context; potential selection bias in “easy” adaptive tasks; and in-process
BackgroundTasks/one-worker execution. A quality gain cannot be attributed to
routing alone if model, context or rubric differs across modes. Publish raw
paired results and missing-data reasons rather than a broad superiority claim.
