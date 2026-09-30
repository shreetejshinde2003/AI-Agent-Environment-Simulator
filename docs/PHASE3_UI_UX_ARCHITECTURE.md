# Phase 3.4 — UI/UX architecture

Date: 2026-09-29. Code baseline: `48ece6d` — deterministic adaptive routing and run UX.

**COMPLETED:** repository UI/data-contract audit and this design specification.
The original architecture-only checkpoint planned the workbench below without
application or execution changes. This document remains the design authority;
checkpoint status notes distinguish what has since been implemented. No model
calls are part of these UI checkpoints.

**Checkpoint 3.4.1 COMPLETED (2026-09-29):** Native labelled modal/focus
containment and return, keyboard picker/graph inspection, reduced-motion rules,
static recorded handoffs, truthful status and loading copy, and small presentation
improvements. The audit table below records the pre-checkpoint baseline.
**PARTIAL:** automated DOM accessibility coverage, screen-reader/zoom and
full contrast verification. The workbench shell and contextual inspector were
subsequently started in 3.4.2; full replay, Compare and major redesign remain
**NOT IMPLEMENTED**.

**Checkpoint 3.4.2 COMPLETED locally (2026-09-29):** A selected-run workspace
now composes the existing RunPicker, actual graph, contextual run/stage/route/
handoff inspector, and a short persisted-event area. Selection targets are
run-scoped UI IDs; REST snapshots remain the execution source of truth. History
opens that same workspace and retains aggregate charts. **PARTIAL:** full Runs
browser, inspector depth, timeline, responsive and page consolidation work.

**Checkpoint 3.4.3 Canvas and Inspector Depth COMPLETED locally (2026-09-30):**
The saved adaptive plan is an inspectable non-LLM canvas node; the text path and
recorded handoffs remain keyboard-selectable. The Inspector now separates run,
stage, route, handoff and final-result views, including real stage timing/model/
token fields, recorded upstream messages, output, failures and downstream
nonexecution. Long text expands safely as React text. Missing measurements remain
Not recorded; actual zero remains zero. Final Result has a dedicated view with
recorded timing, token coverage, stage-attempt/handoff counts and existing exports.
No backend/API/schema change or model call was required. Local read-only fixtures
verified all five inspector views, keyboard and pointer node/handoff inspection,
run switching and reload, picker search, safe long-output keyboard scrolling,
failure evidence, existing navigation, and stacked layout at 1024 × 900 without
horizontal overflow. No task was submitted. Production verification of 3.4.3
remains **PARTIAL**; these are local fixture results. Exact per-stage consumed
input provenance is unavailable; full event correlation/timeline, screen-reader,
zoom and final mobile verification remain **PARTIAL**. The original roadmap below names this canvas
work as 3.4.4; this checkpoint follows the team's 3.4.3 naming, without starting
the separate Runs-browser/composer work.

The team reports production verification of Single, Fixed, Adaptive
(Analysis → Report), and PostgreSQL restart durability. This review inspected
source and public reference documentation; it did not repeat those production
tests. `PHASE3_RESEARCH_ARCHITECTURE.md` still describes Adaptive production
verification as pending; that statement predates the team's latest verification.
Private benchmark provisioning remains **PARTIAL**. Retain the execution and
research contracts in that document; this specification governs their presentation.

## 1. Current UI audit

Findings below come from the current code, not from inferred deployed behavior.
Paths are relative to the repository root; frontend component names refer to
`frontend/src/components/dashboard/` unless qualified otherwise.

| Surface / source | What works now | Friction or integrity gap | Future disposition |
|---|---|---|---|
| `App.jsx`, `layout/AppShell.jsx`, `Sidebar.jsx`, `Topbar.jsx` | Shared selected run across seven pages; real health/socket indicators | Goal, run selector, global totals, page header and actions compete for space; disabled Pause/Stop remain prominent | One run header and workspace; retain secondary catalogue/settings navigation; remove unsupported execution controls from primary chrome |
| `pages/LiveSimulation.jsx` | Graph, result, trace, handoffs, activities and real charts | Six global cards precede the run; an 800px graph, details and charts make a long dashboard | Canvas first, compact run metrics, contextual details |
| `pages/TaskSummary.jsx` | Real persisted history, newest first, readable titles | Repeats all of `SimulationDetails` below its table; selecting history does not itself navigate to Flow | Runs browser selects the same workspace; keep full history as an expanded browser |
| `pages/Agents.jsx` | Real roster and aggregate stage metrics | Intro says five executable agents although Direct is also executable; global agent status is not selected-run status | Retain Agent Catalogue for capabilities/aggregate history; run stage details move to inspector |
| `pages/Messages.jsx`, `Logs.jsx` | Real selected-run messages, events and activities | Duplicate workspace panels and require page switching | Handoffs and activities become filters within Events; old navigation can redirect during transition |
| `pages/Replay.jsx` | Honest event-prefix slider; explicitly says it does not re-run agents | Does not reconstruct graph, outputs or metrics; name in source suggests more than behavior | Retain as Event history until real historical inspection is implemented |
| `pages/Settings.jsx` | Read-only origins; shared-workspace/no-auth disclosure | Supported-behavior text omits Single/Adaptive; persistence text still implies only SQLite and pending production durability | Small About & Connection surface with accurate supported behavior; no cosmetic switches |
| `CreateTaskModal.jsx`, `QuickActions.jsx` | Real mode submission, safe upload limits, benchmark registry, explicit adaptive category, new-run opening | Dense 440px modal; generic Working state; no UI for API-supported optional title; legacy specialist mixed with research modes | Reuse submission path in accessible composer; separate legacy utility |
| `RunPicker.jsx`, `utils/runs.js` | Search, newest-first titles, mode/status/time/ID, native keyboard activation, Escape/focus return | No mode/status filters; opening does not focus search automatically; no custom arrow navigation; selected run absent while initial fetch is pending | Preserve compact picker; reuse row/search logic in Runs panel |
| `AgentRelationshipGraph.jsx` | React Flow, actual stage path, stage/message inspection, real statuses | Inspector below graph; Adaptive decision is absent from graph; edge animates throughout receiver activity after a handoff; no-run fixed preview could resemble a run | Reuse React Flow and backend topology; contextual inspector and explicit decision node; revise motion semantics |
| `TaskDetailsPanel.jsx` | Real result, route reasons, IDs, usage, errors, upload preview, terminal exports | Long metadata list; route capabilities/available inputs and benchmark provenance not shown; result competes with graph | Split into Run/Result/Route inspector content; keep safe text rendering and exports |
| `SimulationTimeline.jsx`, `MessageFlowFeed.jsx` | Actual event timestamps; expandable full handoff text | Multiple nested scrolling areas; text-only events cannot link all objects reliably | Unified trace with event-kind filters, selected-agent filtering and progressive disclosure |
| `StatsCardRow.jsx`, `MetricsCharts.jsx`, `SimulationInfoPanel.jsx` | Aggregates derive from saved stages | Global totals duplicated in sidebar and workspace; chart labels use short IDs; token completeness not explicit | Totals in Runs overview; run metrics near canvas; detailed aggregate charts in catalogue/overview |
| `index.css`, `SimulationWorkspace.css` | Coherent navy base, spacing/radius tokens, focus ring, reduced-motion rule | Many raw hex values and fallback tokens (`--bg-card`, `--bg-elevated`); graph text at 10px; inactive/tertiary text needs contrast review | Consolidate existing tokens and readable sizes incrementally |
| Responsive CSS | Grids stack below 1150px; sidebar becomes icon rail below 900px | Fixed 800px graph remains; toolbar, modal and nested panels need narrow-screen/zoom testing | Explicit workspace collapse model in §27 |
| `components/common/Modal.jsx` | Escape, backdrop close, labelled close button; directive autofocus | No dialog role/name association, `aria-modal`, inert background, focus containment or return-focus handling | Accessibility prerequisite before composer expansion |
| `hooks/useSimulationData.js`, `useLiveSocket.js` | REST polling every 5s; socket triggers refresh; reconnect fetch; stale acknowledged-run protection | Health connection is not initial data load completion; whole run list/payload fetched; generic API errors lose structured route details | Preserve one source of server state; add explicit fetch/selection states before later scale work |
| `frontend/tests/runs.test.js` | Four pure helper tests for merge/title/topology/datasets | No automated DOM tests for modal, picker focus, creation navigation or graph inspection | Add interaction coverage at relevant checkpoints; browser smoke remains required |

Unused/prototype candidates found by import/reference inspection: `services/mockData.js`,
`AgentNode`, `GraphLegend`, `ActivityFeed`, `StatsCard`, `AddAgentModal`,
`pages/PagePlaceholder.jsx`, and `useActivePage`. The active data hook does not
import mock data and sets `isDemoMode: false`; comments about a demo flag are stale.
Some old CSS selectors target these retired components. Do not activate them as
shortcuts. Remove only after a dedicated import/build check in a later checkpoint.
The custom-agent API creates non-executable roster metadata, not new agent logic.

## 2. Design goals

**PLANNED:** make a selected run understandable within one workspace: what was
requested, why this path was chosen, what actually ran, what passed between stages,
what failed, and what the result contains. Preserve automatic creation selection,
reload selection, immutable IDs, uploads, exports and all three research modes.

Success is fewer navigation steps and clearer evidence, not more widgets. A
researcher should reach a stage output, route reason or handoff from Flow with
one selection; open a saved run without losing context; and distinguish missing
telemetry from zero. Quality comparison remains a separately gated research task.

## 3. Product identity and terminology

Keep **Multi-Agent AI Environment Simulator** as the product name. “AI Research
Workbench” describes its interaction model. The team owns execution, data,
visualization and future evaluation in this repository.

Use **Run** for the persisted Task/Simulation object. Use **New Run** and **Run
configuration** initially: one submission creates one run, not an experiment group.
The composer supports experimentation without implying an experiment-management
entity exists. Reserve **Experiment** for a later versioned set of comparable
runs. Label Adaptive as **Adaptive · rule-based**. Keep Individual Specialist in
a clearly named utility section, outside Single/Fixed/Adaptive comparisons.

HR/employee files are benchmark domains. Dataset analysis, workflow testing and
aggregate reasoning examples are appropriate. Candidate screening, hiring,
rejection, employee ranking, suitability and termination recommendations are not.

## 4. Visual-integrity principle

> Every animation, visualization, color, control, and interaction must reveal something about the actual simulation state.

Data integrity extends to visual integrity. Backend records determine route,
stage status, handoff existence, timestamps and metrics. UI selection is a distinct
visual treatment, never execution state. A connection badge means transport/data
availability, not that an agent is busy. A completed run means execution completed,
not that its answer was independently verified.

Do not animate absent messages, infer progress from elapsed time, count skipped
agents as calls, or populate empty charts. Historical inspection must identify
itself as recorded history; it cannot look like a new live execution.

## 5. Information architecture

**PLANNED:** three top-level destinations: **Workspace**, **Runs**, **Agent
Catalogue**; a low-emphasis **About & Connection** utility. Workspace owns Flow
and Events. Runs is an expanded history browser and optional overview, not a
second rendering of every run panel. Catalogue explains available roles and
aggregate execution history. Comparison is introduced only after §15's gates.

Messages, Logs and Event History become contextual Events views. Retain their
existing navigation as temporary redirects until keyboard/browser regression
checks pass. Do not delete their content or exports during migration. Keep a
small product navigation rail separate from the contextual Runs panel.

## 6. Main workspace

Desktop wireframe — all labels below specify UI structure, not sample telemetry:

```text
+----------------------------------------------------------------------------+
| Product   [run title] [mode] [status]  [connection]            [New Run]     |
+--------------------+-----------------------------------+-------------------+
| Runs               | Flow | Events                     | Inspector         |
| [Search]           | run metrics: attempts / time /    | Run / selected    |
| [Mode] [Status]    | recorded tokens / handoffs        | object details    |
|                    |                                   |                   |
| title              |        ACTUAL RUN CANVAS          | context/output    |
| mode status time   |                                   | errors/provenance |
| ...                | [Fit] [Zoom] [Text path]           | [View result]     |
+--------------------+-----------------------------------+-------------------+
| [Recorded timing strip / recent events; expandable]                        |
+----------------------------------------------------------------------------+
```

Keep the canvas visible while inspecting an object. Start the inspector on the
run overview with directive and result access; selecting Goal, Decision, Agent,
Handoff or Result swaps its contents. On completion, announce the result and
provide a visible Result action; do not steal focus from someone inspecting a
stage. Let long output expand into the central pane without changing selected run.
Use one primary scrolling region per pane, not cards nested inside scrolling cards.

## 7. Run browser

Extend the existing picker rather than replacing its reliable creation/selection
path. Compact picker: title, mode, status, local timestamp, secondary ID, search.
Desktop Runs panel: add mode/status filters, optional duration, and expand to full
history. Task type and dataset belong in row details or filters only when useful.
Group Today / Yesterday / Earlier in the user's local timezone if the list is
long; preserve newest-first stable ordering within groups. Search title and ID;
mode/status filters are explicit. Do not invent short display IDs or duplicate
the immutable task identity.

Selection preserves Flow/Events context where sensible and clears an inspector
target from the previous run. New creation always calls the existing
`openCreatedRun(run)` behavior and opens Flow. Keep localStorage as fallback;
plan an optional URL query for run/view so browser back and direct links work
without changing API routes. A missing URL run gets an explicit unavailable
state, not silent substitution with another person's run.

## 8. Experiment composer

**PLANNED:** a wider accessible dialog (roughly 640–720px on desktop), full-screen
sheet on narrow screens. Reuse `CreateTaskModal` state and request semantics.

```text
New Run                                                        [Close]
Goal / directive                 [multiline input]
Title (optional)                 [literal user title]
Execution strategy              (Single) (Fixed) (Adaptive · rule-based)
  Mode description / fixed path / rule-based explanation
Context                          [Add TXT / CSV / JSON]
  filename, prepared preview, truncation notice, [Detach]
Benchmark                        [None / real registered choices]
  safe metadata / explicit unavailable or empty state
Adaptive category                [Infer / supported category]
Utility                          [Individual Specialist, collapsed]
                                 [Cancel] [Start Run]
```

Only include supported controls. API already accepts optional title; preserve
deterministic 80-character display normalization and permanent ID. Explicit
adaptive category overrides inference; this changes an experimental condition
and should remain visible in the submitted run metadata. Explain source material
requirements for summarization without inventing a client-side route preview.
Routing currently occurs within creation; no separate preview/plan endpoint exists.

Distinguish uploading, submitting and validation errors. Files are uploaded and
stored before run creation; Detach only removes their reference, not the stored
upload. Never label it Delete. Existing limits: three files, 256 KiB each,
6,000 prepared characters/file (plus truncation notice), first 20 CSV data rows.
Reference uploads are not automatically anonymized. Keep the shared-workspace
disclosure. Preserve entered fields on failure. A request timeout is an uncertain
submission outcome; reconcile history before encouraging another paid run.

## 9. Simulation canvas

Reuse installed `reactflow` 11.11.x and the stage path in `utils/runs.js`. No graph
library migration or editable workflow engine is required. Keep a top-to-bottom
path, fit-to-view, zoom buttons, stable node positions and a text-path alternative.

| Mode | Planned visible topology | Authority |
|---|---|---|
| Single | Goal → Direct → Result | Stored `stages` |
| Fixed | Goal → Orchestrator → Research → Data → Analysis → Summarizer → Report → Result | Stored stages; explicit non-LLM coordinator annotation |
| Adaptive | Goal → Route Decision → selected stages → Result | Persisted `routePlan` and `stages`; Decision is a plan object, not another agent invocation |
| Legacy specialist | Goal → selected specialist → Result | Stored stage, utility label |

Show selected stages before they execute, labelled Selected / waiting. Executed
means a start is recorded. On inconsistent plan/stage data, show an integrity
notice and actual stage evidence; do not rebuild a guessed path in JavaScript.
For old records without stages, offer recorded result/events plus “Stage topology
not recorded.” For no selected run, use a quiet Create/Open empty state rather
than an apparently running fixed graph. A separate labelled fixed-path diagram
may explain the mode inside the composer.

Edges are either **control/dependency links** or **recorded handoffs**. Only actual
messages carry payload inspection and delivered styling. Goal, Decision,
Orchestrator and Result links are control flow and must not look like LLM messages.

## 10. Node and state semantics

Keep route selection and stage execution as separate dimensions. Backend stage
values currently are `waiting`, `active`, `completed`, `failed`. These visual
labels require no new persisted status enum for current sequential execution:

| Visual state | Evidence | Icon / border / label | Motion |
|---|---|---|---|
| Selected, waiting | Stage row exists; not started; run queued/running | Outline circle; neutral border; “Selected · waiting” | None |
| Running | Stage `active` in a fresh authoritative response | Activity glyph; blue border; “Running” | Optional subtle border pulse while observation remains fresh |
| Completed | Stage `completed` | Check; green border; “Completed” | Brief transition on newly observed completion only |
| Failed | Stage `failed` | Error octagon; red border; “Failed” | None required; error accessible from node |
| Skipped | Agent in `routePlan.skippedAgentIds`; no stage | Minus/slash; dashed border; “Not selected” | None |
| Not executed | Selected stage waiting, no start, run terminal failed | Block/stop outline; neutral/amber accent; “Not executed” | None |
| Unknown/stale | Missing data or connection/data freshness lost | Question/clock; “State unavailable” or “Last known: Running” | Stop execution pulses |

Use a separate focus/selection ring that does not overwrite the status border.
Agent role color may identify a small icon; it must not imply success/failure.
Never reduce skipped text to illegible opacity.

Recommendation: keep skipped agents outside the connected path, in a collapsed
**Not selected (count)** list in the Decision inspector. A later visibility toggle
may reveal this list beside the canvas, but never join it to handoff edges. Web
Search belongs in the catalogue as unavailable, not in the adaptive skipped set
unless the actual plan records it there (current plans do not).

## 11. Router / route-decision visualization

Adaptive gets a small **Route Decision · rules-v1** object. Clicking it displays:
mode, stored task type, ordered selected agents, skipped specialists, required
capabilities, available input names, validation and the stored `reasons`.
Expand technical names on demand; readable labels must preserve the underlying
meaning. Use “Decision summary,” never “Thought process.”

Creation plans and validates synchronously before the queued response; the
persisted `route_planned` event occurs before `simulation_started`. No planning
start event or measured router duration exists. Show **Plan validated**, not a
running router, latency bar, token counter or fictional planning animation. An
invalid plan returns HTTP 422 before a run is saved: display it in the composer,
not as a fabricated failed run. Future structured error rendering can preserve
`detail.code` and `detail.routePlan` through `apiClient.js` without a backend change.

## 12. Contextual inspector

One inspector owns one selection: Run, Goal, Decision, Stage, Handoff, Dataset or
Result. Use a discriminated UI target such as `{kind: 'stage', agentId}` scoped
to the selected run; use message IDs for handoffs. Do not store copies of stages.

**AVAILABLE NOW:** stage name/status, output key/text, model, provider token
fields, timestamps, measured stage duration, latest activity, safe error,
structured `inputError`; run directive, prepared uploads and benchmark context;
incoming/outgoing recorded messages. Show null as Not recorded / Not started.
Output character count can be derived from the displayed text, explicitly labelled
characters, not bytes or tokens.

**BACKEND CHANGE REQUIRED:** exact input binding per historical stage, rendered
prompt size/hash/version, actually consumed source IDs, provider request count
distinct from stage attempts, planning duration. Contracts select preferred
artifacts, and some omit raw upload text when a predecessor exists. Thus “available
run context” and “recorded incoming handoff” must not be called “exact model input.”
Do not reconstruct old prompts with today's contract code and present them as fact.

The inspector starts compact with metadata and output preview. Expand to full text
or open Result centrally. Render all model/upload text safely; preserve current
React text rendering and do not inject HTML.

## 13. Flow view

Flow is the default workspace tab and contains canvas plus contextual inspector.
Header metrics and the selected run do not change when switching views. Controls
are Fit, Zoom, Text path, and expand/collapse inspector; no rearrange-to-execute,
connect-nodes, pause, speed or retry controls. Node/edge selection and a parallel
ordered stage list offer equivalent access.

A compact recorded timing strip may sit below Flow once §16 is implemented.
Before then, show recent real events with an Open Events action. Keep full
transcripts/results out of every node to avoid visual clutter.

## 14. Events view

Use accessible workspace tabs for **Flow / Events**. Events shows persisted run
events in stored order with full timestamp, relative offset and event type. Add
filters: lifecycle, stages, handoffs, activities, errors, selected agent. Separate
RunEvent, Message and Activity sources so one action does not appear as three
identical events. Lifecycle `message_created` can open the handoff list; do not
parse prose as an authoritative message ID.

`RunEvent` has ID/type/time/agent/text, not `stageId`, `messageId`, sequence number
or rich payload. Agent navigation is safe for current unique-agent routes.
Exact event-to-message correlation requires future explicit references; where
ambiguous, show candidates rather than claim a match. Use persisted timestamps,
not socket receipt times. Maintain scroll position; offer “New events” instead
of forcing the view to jump while someone reads earlier events.

## 15. Compare view

**PLANNED / gated:** reserve a workspace destination but do not show an operational
Compare tab until comparison selection and provenance requirements are implemented.
There are objective measurements today, but no experiment group or evaluation
records. An eventual first increment may compare manually selected saved runs,
explicitly labelled **Exploratory comparison**, without pretending they are matched.

```text
Comparison: [selected saved runs / future experiment group]
Conditions: directive, prepared context, dataset checksum, models, route version
                    Single          Fixed           Adaptive
Outcome             [record]        [record]        [record]
Stage attempts      [record]        [record]        [record]
Duration            [record]        [record]        [record]
Recorded tokens     [record/N/A]    [record/N/A]    [record/N/A]
Handoffs            [record]        [record]        [record]
Path                [actual path]   [actual path]   [actual path]
[Open each run / inspect outputs]
```

No sample numbers, winner badges or default “Adaptive is better” conclusion.
Compare known conditions first; surface mismatched directive, input, model or
dataset checksum. Same filename or title does not establish identical input.
Current uploads lack original-content checksums and runs lack complete prompt/
parameter/version provenance. Formal matched groups need backend support, recorded
repetitions and a research protocol. Failed/partial runs remain visible with missing
measurements; do not drop them to improve averages. Legacy specialists are excluded
from the three-mode comparison. Quality fields stay absent until versioned criteria,
evaluator type and real scores exist; the nullable `evaluationScores` placeholder
does not constitute evaluation support.

## 16. Timeline and replay architecture

**PARTIAL data readiness:** current timestamps support a useful recorded stage
timeline and coarse historical inspection; they do not support exact event-sourced
replay of every input/token/UI state. Recommend timeline first, terminal-run
inspection second. No backend snapshots are necessary for that bounded first scope.

Use `createdAt` as timeline origin so `route_planned` can precede execution;
mark `executionStartedAt` separately. Stage intervals use `startedAt` and
`completedAt`; display measured `durationSeconds` separately where available.
Missing ends are open/incomplete, not invented. Router is a timestamp marker,
not a duration bar. Sequential stage bars occupy only their recorded spans.
Handoffs are point events. On restart, recovery may mark an active stage failed
and append only `simulation_failed`, with no `agent_failed` event or measured
duration. Represent the recorded failure boundary and note timing uncertainty.

Future client-side `deriveRecordedState(run, cursor)` is a pure projection over a
frozen terminal snapshot. Stage start/end determines running/completed/failed;
output and token totals reveal only at a recorded terminal boundary, never
gradually. Messages reveal at their own timestamps. Result appears at completion;
downstream becomes Not executed on terminal failure. Event array order breaks
equal-time ties; use event index as the canonical cursor with timestamp display.
Do not assume UUID order encodes causality. Hide unsupported historical fields.

Recorded history controls are labelled Step previous/next, Jump to event and
Return to current record. A later playback timer only advances the inspection
cursor over recorded data; it makes no API execution calls and is explicitly
historical. Start with step controls for a practical B.Tech scope. Do not launch
live re-execution as “Replay.” Full forensic replay later needs sequence numbers,
message/stage references, event schema versions and input/provenance snapshots.

## 17. Metrics placement and handoff inspection

Run header: mode/status, stage attempts, measured terminal duration, recorded token
sum and handoffs. Context disclosure: dataset, task type, model(s), creation time
and technical ID. Node inspector: stage tokens, measured duration, output and
error. Runs overview: total/completed/failed, success denominator, average measured
terminal duration; optionally measured tokens. Catalogue: per-agent aggregates.
Move current charts out of the primary Flow canvas; no additional BI dashboard.

`agentInvocationCount` counts stages whose `startedAt` exists, including contract
failures before an API request. Prefer “Stage attempts” with an explanation over
“Groq calls.” Handoffs are real `messages.length`. Token sum must show coverage
when only some attempted stages have non-null values. `llm_client.py` currently
substitutes zero when provider usage is absent; a future measurement change is
needed to distinguish that from true zero. Do not claim fully audited token
coverage or cost savings. Null duration is not zero; live display may say Running
since [timestamp], with no predicted completion or synthetic progress rate.

Handoff rows: sender → receiver, output key, timestamp, derived character count,
short preview; select for full content and ID. A difference between message time
and stage completion can be labelled “Recorded scheduling gap,” not network/model
latency. No delivered/read acknowledgement exists beyond the message record.

## 18. Dataset experience

Keep uploads and registered benchmarks separate. Benchmark labels remain
Employee/HR · Small/Medium/Large, with record count secondary. Only active registry
entries become choices. Show loading, failed registry request, empty registry,
inactive dataset and run-creation validation failure distinctly.

Safe metadata: family, variant, count, import timestamp, checksum, active flag and
schema names/types. Listing a sensitive column name is not permission to expose
its values. The API's `quality` identifies protected/confidential columns; an
explicit allowed-context field policy is not exposed as structured metadata.
Inspect the saved `benchmarkContext` as actual aggregate context; a future backend
policy descriptor is preferable to duplicating `SAFE_FIELDS` in the frontend.
Current employee aggregate fields: Department, JobRole, JobLevel, YearsAtCompany;
HR: Department, JobRole, Status. No individual rows or employment scores.

Existing metadata does not prove that its private file is presently mounted or
checksum-valid; creation performs that validation. Label “Registered / active,”
not “File verified now.” Historical task checksum/context remain evidence even
if today's registry changes. Private production provisioning is **PARTIAL** and
manual; link administrators to `PHASE2_DATABASE_DEPLOYMENT.md`. The normal upload
path is not a benchmark registration mechanism and does not inherit its field
redaction. Never suggest uploading private HR raw files as a workaround.

## 19. Failure states

Failure banner identifies the run outcome and real error, with Open failed stage.
Completed predecessors remain completed. A failed stage is red; selected downstream
stages without starts are Not executed; route-skipped agents remain Not selected.
Final Result says No final result, with partial stage outputs still inspectable.
Derive this presentation from existing fields without writing new statuses.

Use structured `inputError` for actual missing-input details; avoid hardcoded
messages saying Analysis always requires `structured_data`, which contradicts
the flexible contract. Invalid route/input rejected at creation stays a form
error. Distinguish execution failure from inability to fetch the record. Provide
Inspect / Export for terminal runs; no retry button or automatic rerun.

## 20. Empty, loading and connectivity states

| Condition | Planned presentation / action |
|---|---|
| Initial fetch pending | Loading run records; neutral skeleton only; no zero totals asserted |
| No simulations after successful fetch | No simulation data yet; New Run |
| Queued | Saved, waiting to start; selected route visible without motion |
| Router planning | No persisted live state exists; creation may say Validating request, never show an agent planning bar |
| Running | Actual active stage and completed count; no invented ETA |
| No benchmark entries | Existing explicit deployment-registration explanation; context-free runs still allowed |
| Dataset unavailable | Real validation error and preserved form; no silent dataset removal |
| REST unavailable | Last saved view marked stale; retry fetch; New Run disabled |
| Socket reconnecting, REST works | Live events reconnecting; polling active; retain authoritative results |
| Health up, run fetch failed | Data unavailable/stale, not Connected-only reassurance |
| No selected object | Run overview with directive/result access in inspector |
| No events/handoffs | No recorded events; single runs explain their zero handoffs |
| Failed | Evidence-backed failure presentation from §19 |
| No comparison group | Future Compare explains missing selection/group; no populated charts |
| Referenced run missing | Run unavailable; choose from history; no silent replacement of a deep link |

Add frontend `hasLoaded`, fetch status and last successful refresh time; health
alone does not establish data readiness. Freeze “last known” active motion on
lost freshness. Neither a websocket reconnect nor a refresh re-executes a run.

## 21. Design system

Retain the existing near-black navy palette and Inter/system sans-serif with
monospace technical values. Consolidate current tokens rather than introducing a
parallel theme. Keep subtle surface hierarchy, indigo interaction, semantic status
borders, thin edges and restrained grid. Use plain surfaces with minimal gradients
or transparency. Do not import an entire component framework for this layout.

## 22. Typography

Use 14–16px reading/form text, 12–13px secondary metadata, 18–24px headings, and
13px or larger code/ID values at default zoom. Avoid current 10px node status
labels for essential information. Body line height 1.5–1.7; constrain expanded
results to a readable line length. Monospace is for IDs, timestamps and raw payloads,
not whole prose reports. Long titles wrap with an accessible full-text view;
hover-only tooltips cannot be the only way to read a directive.

## 23. Spacing and layout

Reuse the 4/8/12/16/20/24/32px spacing scale and 6/10/14px radii. Use 12–16px
row padding, 16–24px pane padding and a consistent 1px border hierarchy. Desktop
Runs is approximately 240–280px, Inspector 320–380px, Canvas flexible. Do not
enforce all three when the canvas becomes unreadable. Prefer viewport-relative
canvas height with a practical minimum over fixed 800px; retain a normal page
scrolling fallback at zoom. Resizing panels is optional, not an initial prerequisite.

## 24. Color semantics

Reuse navy surfaces (`--bg-app`, `--bg-panel`, `--bg-panel-raised`) and indigo
interaction. Running blue, completed green, failure red, waiting neutral,
not-executed neutral/amber are paired with icon and text. Agent role hue is
secondary identity only. Skipped is dashed/labelled, not a dim success state.
Replace scattered fallbacks/hex values gradually. Validate contrast in every
state; existing tertiary text is not assumed to pass. Targets: 4.5:1 normal text,
3:1 large text and meaningful UI boundaries, with clearly visible keyboard focus.

## 25. Motion system

**PLANNED:** interaction transitions 100–160ms; inspector/panel movement 160–220ms;
newly observed status emphasis 180–300ms. Use ease-out for entry, gentle ease-in-out
for an optional running indicator. No bouncing, floating cards or perpetual particles.

The current receiver-active animated handoff edge must become a static delivered
edge. A message is stored as a point event; there is no transfer-duration telemetry.
At most use a brief “new handoff recorded” emphasis on a newly observed message ID,
never a continuous travel animation claiming live transmission. Initial load and
reconnect must not replay old handoffs as new activity. Prefer static edges until
event novelty is tracked reliably. Pulse only a fresh actual active stage; a
validated Router decision has no execution pulse. Completion changes once, driven
by state. Reduce motion removes pulse, travel and panel transforms while retaining
text/icon/border updates. Persisted metrics change directly, without count-up loops.

## 26. WebGL decision

**NOT RECOMMENDED:** WebGL, shader backgrounds, 3D worlds, permanent particles or
GPU-heavy launch effects. Existing React Flow plus CSS is sufficient for six or
fewer agent nodes. A static subtle grid communicates topology with lower cost.
The core remains readable without animation or special graphics hardware.

## 27. Responsive behavior

| Width / context | Layout |
|---|---|
| Large desktop, roughly ≥1440px | Runs + Canvas + Inspector; optional bottom trace strip |
| Laptop, roughly 1024–1439px | Compact picker or collapsed Runs; Canvas + collapsible Inspector |
| Tablet, roughly 768–1023px | One primary view; Runs overlay and modal inspector drawer; explicit close/back |
| Narrow/mobile, <768px | Run list → run view; ordered stage list by default, optional graph; full-width details |

Breakpoints respond to content and zoom, not device labels alone. Keep result,
errors, mode, route and exports accessible on mobile. Use touch targets of at
least 44px where practical. Do not force horizontal scrolling for the whole app;
only graph/data regions may pan with an equivalent text view. Test 320/375px,
768px, laptop and desktop widths, plus 200% zoom and reflow at higher zoom.

## 28. Accessibility

**COMPLETED in 3.4.1:** visible focus styling, labelled native dialog with inert
background, initial focus, trapped Tab / Shift+Tab, Escape, focus return,
keyboard picker/graph inspection, status labels, and reduced-motion support.
**PARTIAL:** screen-reader, contrast, narrow-screen/zoom and automated DOM
interaction coverage still need dedicated verification.

Use a labelled modal dialog with inert background, initial focus, trapped Tab /
Shift+Tab, Escape and focus return. After successful creation move focus to the
new run heading because the workflow changed; after cancellation return to the
trigger. During submission, announce busy state without pretending close cancels
an in-flight execution. Test the actual focus sequence and double-submission guard.

Use true tabs with keyboard behavior for Flow/Events, semantic buttons for picker
items, current-selection labels and a search focus target. Either implement and
test listbox arrow behavior fully or retain the simpler search-plus-buttons
pattern; do not assign unsupported ARIA roles. Graph nodes and handoffs need
keyboard access and the equivalent stage/message list. Current custom node
buttons are useful; React Flow node focus is disabled, so validate focus behavior
rather than assuming library defaults solve it. No mouse-only edge inspection.

Announce status transitions politely and errors appropriately, without announcing
every poll or token change. New data must not steal focus. Add skip links, named
regions, visible status labels, readable timestamps, contrast checks, reduced
motion, browser zoom and screen-reader testing. Follow the
[WAI modal dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/).
Current [React Flow accessibility guidance](https://reactflow.dev/learn/advanced-use/accessibility)
is a design reference; verify APIs against installed v11 before implementation.

## 29. Component architecture

Keep `SimulationProvider` and API boundary. Introduce composition gradually:

```text
App / AppShell
  RunHeader (connection + current run + New Run)
  RunWorkspace (evolution of LiveSimulation / SimulationDetails)
    RunsPanel / existing RunPicker
    WorkspaceTabs
      Flow: SimulationCanvas (existing AgentRelationshipGraph)
      Events: EventFeed (existing SimulationTimeline + handoffs/activity)
    InspectorPanel
      Run/Result content (from TaskDetailsPanel)
      RouteDecision content
      Stage content / Handoff content
    RecordedTimeline (later)
  CreateTaskModal → RunComposer
  RunsOverview (existing TaskSummary)
  AgentCatalogue (existing Agents)
  AboutConnection (existing Settings)
  CompareView (gated later)
```

Keep Card, Button and safe output rendering; repair Modal before reuse. Extract
RunList rows/search when both picker and panel use them. Extract DatasetSelector
only because registry fetch/preview/empty states form a coherent responsibility.
Keep inspector variants in one module initially unless complexity warrants files.
Move graph projection/state derivation into pure utilities for deterministic tests.
Retire duplicate page renderings and unused prototypes after parity, not in one
large rewrite. No new graph/store/design-system dependency is justified now.

## 30. Frontend state architecture

| State | Owner / source | Rule |
|---|---|---|
| Tasks, stages, route plans, messages, events, metrics, roster | Existing data hook; authoritative REST | One cached server representation; inspector/graph derive from it |
| Socket and REST health/freshness | Existing hooks plus explicit fetch status | Socket invalidates/refetches; it is not a second execution store |
| Selected run | SimulationContext, ID only | Preserve immediate accept/select/open; localStorage fallback; optional URL later |
| Selected object | RunWorkspace | Scoped kind/ID; clear on run change; no duplicated output data |
| Flow/Events view | Workspace/URL UI state | Independent of execution; does not alter backend mode |
| Run query/filter/panel open | Runs UI | Local interaction state; optional persistence for harmless preferences |
| Composer draft/uploads | Composer | Request state separate from persisted run; detach ≠ server deletion |
| Recorded cursor | Timeline UI | Terminal snapshot projection; never mutates live Task |
| Comparison selection | Future Compare UI, IDs only | Groups/protocols need later backend persistence |

Retain `acceptRun`/`mergeRuns` to avoid stale fetches losing newly created runs.
Its event-count monotonic check is a pragmatic guard, not a universal record
version. A future deletion API or eventless record edits require version/tombstone
support. Do not introduce Redux/Zustand or copy Task into graph node state as a
second authority. Multiple requests should coalesce as today; later large-history
work should split summary fetching from selected-run detail without changing
these ownership rules. Pure projection helpers can normalize `/tasks`
`in_progress` versus `/simulations` `running`; keep one frontend source initially.

## 31. Backend/API gap analysis

Current application endpoints are under `/api/v1`; health is `/health`, live
notifications `/ws/live`. Read-only layout work needs no schema migration.

| Proposed data/feature | Status | Existing source or required future work |
|---|---|---|
| Run title/ID/directive/mode/status | AVAILABLE NOW | `GET /tasks`, `/tasks/{id}`; `title`, `executionMode`, lifecycle fields |
| Creation, immediate selected run | AVAILABLE NOW | `POST /tasks`; queued response accepted by `openCreatedRun`; `/simulations` is a compatible projection |
| Real topology/stage states | AVAILABLE NOW | `Task.stages[]`; use run stages, not global `/agents/relationships` fixed topology |
| Selected/skipped/reasons/validation | AVAILABLE NOW | `Task.routePlan`; absent for Single/Fixed/old records; do not invent adaptive decisions |
| Model/input-output-total tokens/stage timing | AVAILABLE NOW, measurement caveats | `StageExecution`; null allowed, usage-missing zero ambiguity noted in §17 |
| Task duration and global/per-agent metrics | AVAILABLE NOW | `elapsedSeconds`, `/simulations/metrics`, `/simulation/stats`, `/agents/stats`; no price/cost metric |
| Handoffs and payload | AVAILABLE NOW | `Task.messages`; `/messages?simulation_id=...`; no transport timing/acknowledgement |
| Events and activity | AVAILABLE NOW | `Task.events`, `Task.activities`, `/simulations/{id}/events`; `/simulation/activity` |
| Error and missing-input details | AVAILABLE NOW | Task/stage `error`, `inputError`; API client needs to retain structured 422 details |
| Roster/catalogue | AVAILABLE NOW | `/agents` and stats; global active status must not drive a historical run node |
| Typed capability catalogue | BACKEND CHANGE REQUIRED | `contracts.py` exists internally but is not exposed as a structured API |
| Upload context/previews/truncation | AVAILABLE NOW | `POST /uploads`, `/uploads/{id}`, embedded `Task.uploads`; no upload-delete API |
| Benchmark metadata and saved context | AVAILABLE NOW | `/datasets`, `/datasets/{id}`, Task dataset ID/checksum/benchmarkContext |
| Safe-field policy and private file health | BACKEND CHANGE REQUIRED | Structured allowed-context fields and availability/checked-at metadata; registration active flag is insufficient |
| Terminal TXT/JSON/CSV export | AVAILABLE NOW | `/simulations/{id}/export?format=...`; current exports remain supported |
| Recorded stage timeline | AVAILABLE NOW for derived view | Start/end timestamps; missing/inconsistent intervals must remain unknown |
| Exact router duration/live planning | BACKEND CHANGE REQUIRED | Planning span/start/end or measured duration; do not simulate this state |
| Exact stage input provenance/size | BACKEND CHANGE REQUIRED | Persist binding/source references and prompt metadata, with privacy-conscious capture policy |
| Exact forensic replay | BACKEND CHANGE REQUIRED | Versioned event sequence, causal references, structured changes, complete recovery events |
| Exploratory objective comparison | AVAILABLE NOW as manual derivation | Real saved runs; cannot assert matched conditions or statistical superiority |
| Formal experiment groups/repetitions | BACKEND CHANGE REQUIRED | Versioned scenario/input hashes, group/run-number, prompt/model parameters and run linkage |
| Quality/evaluation results | BACKEND CHANGE REQUIRED | Actual evaluator, rubric/version, result provenance, API; placeholder score field is unused |
| Large searchable history | BACKEND CHANGE REQUIRED when scale demands | Paged summary/filter endpoints; currently full run payloads are fetched every refresh |
| Guaranteed no duplicate paid submission | BACKEND CHANGE REQUIRED | Idempotency key/reconciliation semantics; no automatic retry in UI |

WebSocket frames use `{event,data,timestamp}`. Persisted events include
`simulation_created`, `route_planned`, `simulation_started`, `agent_started`,
`agent_completed`/`agent_failed`, `message_created`, and terminal simulation events.
`task_updated`, `task_created`, `message_sent`, `activity_event`, `stats_updated`
also notify clients. The current socket hook ignores frame contents and refreshes
REST. Preserve that correctness first; richer transport consumption is optional
and must deduplicate IDs/reconcile after reconnect. Socket receipt is not a durable
timeline timestamp.

## 32. External reference principles

Public pages reviewed 2026-09-29. These are design inputs, not dependencies,
copied interfaces, or evidence of capabilities in this repository.

| Reference | Observed pattern | Applicable design decision |
|---|---|---|
| [FutureAGI simulation overview](https://docs.futureagi.com/docs/simulation/) | Inspectable simulation runs and evaluation are distinct parts of a test loop | Keep recorded execution evidence separate from future quality scoring |
| [LangWatch Scenario visualizer](https://langwatch.ai/scenario/visualizations/) | Searchable runs with detailed messages and decision/tool inspection | One Runs browser leading to a contextual trace; no need to adopt its service |
| [Talkdesk Simulator](https://support.talkdesk.com/hc/en-us/articles/52487140094875-AI-Agent-Platform-Simulator) | Pre-deployment scenario tests and inspection of orchestration behavior | Expose route metadata and handoffs; do not copy conversation UI or internal-thought terminology |
| [OpenTrain agent simulations](https://www.opentrain.ai/solutions/agent-simulations/) | Scenario design and trajectory review are explicit work | Treat task design/review as team responsibilities; this page is a talent service, not an application architecture |
| [UCP Tools FastUCP guide](https://ucptools.dev/guides/fastucp) | Distinguishes available capabilities, setup-dependent telemetry and gaps | Label unsupported data and provisioning status precisely; commerce flows are outside scope |
| [TensorFlow Playground](https://playground.tensorflow.org/) | Controls, model structure and observed outputs share a visible workspace | Keep supported run conditions near actual execution/results; do not copy training controls into an LLM simulator |
| [React Flow accessibility](https://reactflow.dev/learn/advanced-use/accessibility) | Graph interaction must support keyboard/screen-reader access | Reuse installed graph infrastructure and supply textual alternatives; verify version-specific APIs |

Spacing/hierarchy principles from dashboards are useful, but HR dashboard layouts
are not the product model. No logos, branding, commercial SaaS scope, hidden
backend, external evaluator or hosted simulator is assumed.

## 33. Features explicitly rejected

**NOT RECOMMENDED** for this project phase: 3D worlds, agent avatars, gamification,
permanent WebGL, arbitrary drag-and-drop workflow construction, full no-code
editing, a chat-product clone, chain-of-thought viewing, a large BI dashboard,
billing, collaboration/admin suites and complex settings. They either do not
explain actual research behavior or require substantial new execution semantics.

**NOT IMPLEMENTED:** evaluation engine, formal comparison groups, full replay,
LLM routing, LangGraph runtime, authentication, Web Search, retries and pause/
cancellation. Do not show their controls as operational. Authentication remains
a separate future security phase; this design does not attempt to replace it.

## 34. Academic value

Conservative project wording: “The system provides an inspectable environment
for executing and examining single-agent, fixed multi-agent and rule-based
adaptive workflows. Its interface links recorded routes, stage outcomes,
communication and resource measurements, supporting reproducible analysis and
future controlled comparisons.”

Dynamic path visualization demonstrates what adaptation actually changed;
handoff inspection helps examine information preservation; failure presentation
separates selection from execution; comparison provenance prevents misleading
efficiency claims. UI polish itself is not AIML novelty. Better interpretability
or usability requires a measured study; adaptive quality/superiority remains an
unanswered research question. The team must implement the experiment/evaluation
workflow before claiming that contribution.

## 35. Safe implementation roadmap

Checkpoints below are individually testable, deployable and
reversible. No execution changes are required for the core workspace. Preserve
the old composition until each replacement has parity; remove duplicate navigation
only after its content is reachable. Each checkpoint needs relevant tests,
frontend build/lint, diff review and a narrow production verification using saved
runs. No paid call is required for these UI checks.

### 3.4.1 — Accessibility and presentation foundations

**COMPLETED:** frontend-only foundation; no execution or API changes. The
recorded-handoff edge is static even when its receiver is running; status is
communicated with text and styling. Unsupported Pause/Stop controls were removed.
Native dialog and picker/graph keyboard behavior were checked locally against a
read-only fixture. Further screen-reader and zoom checks remain **PARTIAL**.

- **Goal/files:** repair `common/Modal.jsx`, focus behavior and shared tokens;
  correct Agents/Settings copy, remove primary unsupported Pause/Stop controls.
- **Backend:** none. **Tests:** DOM/browser dialog focus, busy state, Escape,
  focus return, contrast/reduced motion; existing four helper tests/build/lint.
- **Visual acceptance:** same functional composer, readable focus/text, accurate
  mode/persistence descriptions, no lost action.
- **Rollback:** isolated common-component/CSS/copy changes. **Risk:** focus
  regressions in shared modal; test every caller. **Production check:** yes,
  open/close composer and inspect existing records without submitting.

### 3.4.2 — Run workspace shell and state ownership

**COMPLETED locally:** selected-run header and Runs/Flow/Inspector/Events shell;
one existing picker, run-scoped UI target state, truthful graph and persisted
events, run-level default inspector, keyboard-selectable stage/handoff/route
inspection, and basic responsive stacking. Aggregate charts moved to History;
History selection opens the same workspace. REST remains authoritative and the
socket still invalidates/refetches it. No backend, schema or execution change.
**PARTIAL:** the Runs area is still the compact picker, the inspector is an
initial data view, Events shows recent records rather than a full timeline,
legacy pages remain, and narrow-screen/zoom verification is incomplete.

- **Goal/files:** `App.jsx`, `AppShell`, `Sidebar`, `Topbar`, `LiveSimulation`,
  `SimulationDetails`, context/data hooks; introduce RunWorkspace/header and
  explicit loading/freshness UI. Keep data fetching/execution contracts intact.
- **Backend:** none. **Tests:** run selection, stale refresh, reconnect, no-run,
  initial loading and per-run inspector reset; browser back if URL state added.
- **Visual acceptance:** one selected run, title/mode/status visible, canvas first,
  no global metrics dominating Flow; stored selection survives reload.
- **Rollback:** switch composition back to existing pages; no data migration.
  **Risk:** selection races and hidden content. **Production check:** yes,
  reload/navigate between saved Single/Fixed/Adaptive/legacy runs.

### 3.4.3 — Runs browser and composer

- **Goal/files:** `RunPicker`, `TaskSummary`, `CreateTaskModal`, `QuickActions`,
  `utils/runs.js`; shared RunList/DatasetSelector, wider composer and filters.
- **Backend:** none for supported fields; preserve structured API errors in
  `apiClient.js`. Do not implement a preview router or idempotency service here.
- **Tests:** filter/search/focus, real registry empty/error/populated responses,
  title/ID preservation, mocked creation from history immediately opens Flow,
  input validation/upload detach, timeout handling without automatic resubmit.
- **Visual acceptance:** title primary; all three modes clear; utilities separate;
  truthful context limits and no fake benchmark options.
- **Rollback:** restore compact picker/composer UI; existing payloads unchanged.
  **Risk:** accidental duplicate submission, transient registry errors.
  **Production check:** yes, saved runs and registry read-only; creation tested
  with mocked local backend, paid production creation only if later authorized.

### 3.4.4 — Canvas projection and contextual inspector

**COMPLETED locally under checkpoint 3.4.3:** saved plan inspection, deeper
run/stage/handoff/result evidence, safe expandable output, failure context and
keyboard text-path selection. **PARTIAL:** final visual/zoom verification and
screen-reader/zoom/mobile verification and precise consumed-input or
event-to-message provenance, which are not persisted. A laptop-width fixture
check passed; this does not establish complete responsive accessibility.

- **Goal/files:** `AgentRelationshipGraph`, `TaskDetailsPanel`, `SimulationDetails`,
  workspace CSS and pure graph/state helpers; add route-decision node, selected/
  skipped/not-executed semantics, keyboard-equivalent stage/handoff lists.
- **Backend:** none for documented fields. **Tests:** all three modes plus legacy,
  queued/active/completed/failed/recovered/old missing-stage records, exact skipped
  separation, message navigation, safe result rendering, run switch reset.
- **Visual acceptance:** topology matches backend; router has no fake call/time;
  failed downstream is Not executed; outputs inspectable without page change;
  recorded handoff edges do not continuously animate.
- **Rollback:** keep current graph/details as a composition boundary. **Risk:**
  confusing UI selection with status or losing access to output. **Production
  check:** yes, existing adaptive two-stage and fixed/single records.

### Next team checkpoint 3.4.4 — recommended scope (planning only)

**NOT IMPLEMENTED:** a bounded Events/workbench consolidation checkpoint with
live-interaction polish. The original roadmap's canvas/inspector work above was
completed under the team's 3.4.3 name; reconcile the next implementation brief
with the Events and recorded timing scope below rather than repeating canvas work
or renumbering the entire roadmap. Compare remains gated on experiment/evaluation
readiness and is **NOT RECOMMENDED** as the next implementation checkpoint.

- Reuse the selected run's existing events/messages/activities in one contextual
  Events surface, with source-kind filters and safe links to recorded objects.
  Keep Logs/Messages/Event History reachable until equivalent behavior is tested.
  Events currently have agent IDs but no explicit message reference; do not infer
  exact causal links from prose or invent event/message identities.
- Keep Runs selection/context ownership; the compact picker is still a limited
  Runs browser. Avoid introducing competing selected-run state or a new store.
  Reduce repeated route/result information only after preserving access to it.
- Add interaction coverage for focus after internal Inspector links, run-switch
  scroll/export-state isolation, graph fitting across different path lengths,
  socket-driven refresh, and narrow-screen/zoom behavior. Current render tests
  verify content/semantics but do not exercise React effects or native focus.
- Review nested scrolling, screen-reader announcements, focus order, output
  contrast and long-record performance. Full collapsed text is still in the DOM;
  consider mounting it only when expanded if measured payloads warrant it.
  The local development fixture also emitted React Flow's node-type warning
  during navigation despite the existing module-level `NODE_TYPES` constant.
  No broken inspection was observed; the warning's cause remains unverified.
- Full-history polling and duplicated output payloads may become a scale limit.
  Pagination/detail fetching requires a separate additive API design checkpoint;
  keep backend execution and persistence unchanged during UI consolidation.
- Import-audit stale prototype components/styles before any removal; do not
  activate mock data. Consolidate duplicate formatting helpers only where their
  semantics match. No dead-code deletion or new implementation is part of 3.4.3.

### 3.4.5 — Events and recorded timing

- **Goal/files:** `SimulationTimeline`, `MessageFlowFeed`, `Logs`, `Messages`,
  `Replay`, workspace; one Events tab, filters and measured stage intervals.
- **Backend:** none for basic timeline; explicit event references are a separate
  future additive change, not invented here.
- **Tests:** timestamps/ties, no duplicate activity/message presentation, missing
  timing, restart failure, scroll retention, keyboard event navigation.
- **Visual acceptance:** chronological evidence readable; no router duration bar;
  old pages redirect only after parity. **Rollback:** restore separate page
  entry points while keeping the same records. **Risk:** misleading temporal
  precision. **Production check:** yes, saved success/failure traces.

### 3.4.6 — Optional recorded-state inspection

- **Goal/files:** pure `deriveRecordedState` helper, existing Replay/timeline,
  Canvas/Inspector; event-step inspection of terminal runs only.
- **Backend:** none for bounded reconstruction; forensic replay is deferred.
- **Tests:** start/end boundaries, equal timestamps, missing events, restart
  recovery, hidden future outputs/tokens, cursor state never mutates live records.
- **Visual acceptance:** clearly Recorded history; no API calls to run agents;
  Return to current record; honest partial-history labels.
- **Rollback:** remove scrub/step projection, retain Events and timeline.
  **Risk:** exposing final data too early or implying precise replay. **Production
  check:** yes, read-only existing terminal traces. Skip this checkpoint if scope
  pressure threatens core accessibility or graph correctness.

### 3.4.7 — Responsive, failure and motion completion

- **Goal/files:** workspace/layout/common CSS and state presentations across
  Canvas/Inspector/Composer/Events; small event-driven transitions only.
- **Backend:** none. **Tests:** browser at target widths/zoom, keyboard-only and
  screen reader, reduced motion, disconnect/reconnect, missing data and failures;
  mocked integration plus existing frontend regression suite.
- **Visual acceptance:** critical information available on narrow screens, no
  page-wide overflow, no fake motion on load/reconnect, static fallback complete.
- **Rollback:** responsive/motion styles can revert without altering server state.
  **Risk:** CSS collision and focus loss on pane collapse. **Production check:**
  yes, desktop/mobile saved records, no new paid runs.

### Later gated checkpoint — Objective comparison

- **Goal/files:** future CompareView and Runs selection, derived metric helpers;
  formal experiment backend added only under its own research checkpoint.
- **Dependencies/backend:** exploratory manual records need no new endpoint;
  matched experiments need versioned group/provenance/input metadata and tests.
  Evaluation scores have an additional evaluator gate.
- **Tests:** incompatible conditions flagged, null/partial usage, failures retained,
  mode separation, no automatic winner, persisted group tests when groups exist.
- **Visual acceptance:** measured columns plus actual paths and explicit comparison
  limits; no fabricated sample values. **Rollback:** hide Compare while runs and
  metadata remain readable; additive schema only after a separate review.
- **Risk:** invalid scientific comparisons. **Production check:** yes, only after
  its backend gate; historical read-only comparison requires no Groq call.

## 36. Risks and limits

The largest risks are presenting available context as consumed input, counting
stage attempts as provider calls, animating old handoffs as live traffic, and
equating successful execution with answer quality. Current token-usage fallback,
missing prompt provenance and inconsistent recovery-event granularity limit
research claims and replay precision.

Full Task payload polling will become expensive with large history; do not solve
that by discarding evidence silently. Shared unauthenticated data remains visible
to backend users; a polished workbench does not provide access control. Background
execution remains in-process and cannot resume interrupted model calls. Private
benchmark files require deployment provisioning independent of PostgreSQL records.
Single/Fixed/Adaptive measured differences may reflect prompts, models and task
conditions as well as route length. No UI can substitute for a controlled study.

## 37. Acceptance criteria and phase completion

For later implementation acceptance:

1. Existing Single, Fixed, Adaptive and legacy records open and export; no schema
   rewrite, model call or execution side effect comes from viewing them.
2. Creation acknowledgement immediately selects the new run; stale refresh cannot
   replace it; reload restores its ID and title.
3. Canvas path equals stored selected stages; Decision/Orchestrator are visibly
   non-LLM; skipped agents never receive executed styling or telemetry.
4. Selected, running, completed, failed, skipped and not-executed are distinguishable
   with text/icon and keyboard access, independent of color.
5. Route reasons, outputs, handoffs, real errors and result remain reachable from
   the same workspace; exact input provenance is not fabricated.
6. Timeline uses recorded timestamps; historical mode hides future output and is
   visibly separate from live view; no imaginary router duration or streamed tokens.
7. Metrics disclose missing/partial coverage; no predicted progress, quality scores
   or superiority claims appear without data and evaluation support.
8. Dataset zero/error/registered states reflect the API; private fields never become
   employment decision controls; uploads and safe benchmarks remain distinct.
9. Modal/picker/tabs/graph inspection work by keyboard, focus returns predictably,
   reduced motion is respected, and narrow-screen/zoom layouts retain all evidence.
10. Comparison stays gated; legacy utility execution, unsupported features and
    backend limitations are named accurately.

**COMPLETED in this phase:** source audit, information/component/state architecture,
API gap analysis, reference review, staged acceptance plan and checkpoints 3.4.1
and 3.4.2, plus checkpoint 3.4.3 Canvas and Inspector Depth locally. **PLANNED:**
the remaining interface composition. **PARTIAL:** final Runs/Inspector/Events
design, exact stage-input provenance, page consolidation, responsive verification,
production benchmark provisioning and formal comparison data readiness.
**NOT IMPLEMENTED:** Compare, evaluation UI, full replay or the final polished
workbench. **NOT RECOMMENDED:**
WebGL/no-code workflow/HR decision-product scope.

The original architecture-only checkpoint used `git diff --check` and
`git status --short`. Checkpoints 3.4.1 and 3.4.2 additionally validate frontend
tests/build/lint and backend tests/compile. AGENTS.md, environment values,
backend logic and deployment configuration remain outside these UI checkpoints.
Checkpoint 3.4.3 final validation: 30 frontend tests pass (including render-level
Inspector and missing-versus-empty handoff coverage); production build passes;
lint has zero errors and the two existing Fast Refresh warnings. All 59 backend
tests and backend compilation pass; the existing Starlette/AnyIO deprecation
warning remains. `git diff --check` passes. No Groq call, commit, push or staging
is part of this checkpoint. Compare, replay and evaluation UI remain
**NOT IMPLEMENTED**.
