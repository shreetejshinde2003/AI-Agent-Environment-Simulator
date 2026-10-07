# Pre-release UX and output consolidation acceptance

Accepted locally on 8 October 2026 (Asia/Kolkata). This is consolidation after
Phase 10, not a new feature phase. Starting HEAD:
`5e4df38a31855c683839652c89e9079677167a64`; initial status contained only
untracked `AGENTS.md`. Both local databases read schema 13. No schema bump, new
persistence table, mode/routing change, production graph activation, live provider
request, push, deployment or Railway change was made. AGENTS.md was never edited,
staged, renamed, committed or deleted. Historical acceptance reports are untouched.
The implementation/acceptance commit is identified by the local Git history entry
`fix: consolidate run UX and preserve output intent`.

## Audit and corrections

All eleven original destinations were manually exercised before editing:
Live Simulation, Research Lab, Simulation History, Agents, Messages, Logs,
Event History, HR Hiring, Organizations, Recycle Bin and Settings. Header/workspace
selector/totals, selected-run context, graph, inspector, output, empty states and
history metrics were inspected. New-run/removal/focused-reading dialogs were
subsequently exercised in the same disposable acceptance workflow.

| Area | Before | Accepted behavior |
| --- | --- | --- |
| Navigation | Eleven destinations, three overlapping evidence screens | Eight: Live Simulation, Simulation History, Research Lab, Agents, HR Hiring, Organizations, Recycle Bin, Settings. Handoffs/events/history stepping belong to selected-run details. |
| Original intent | Immutable context was already present; no directive mutation found. Entire predecessor responses entered prompts; later source context was omitted | Original request remains authoritative; stage objective and subordinate bounded predecessor input are explicit; final synthesis retains original sources and constraints. |
| Prompts | Report forced plain text/headings; Research/Summarizer capped all requests at 200 words | Requested format wins; shortest complete response, no boilerplate/task redefinition; no universal 200-word cap. |
| Output | Literal Markdown/serialization, small inspector panes and nested scrolling | Full-width final reading; safe Markdown rendering, formatted JSON, plain text; Raw/copy/focused dialog; explicit contract problems. |
| Live | Run list, graph, metadata/output inspector and events expanded together | Run → graph → one of Overview/Output/Handoffs/Events/Technical details. Intermediate previews expand explicitly; final answer is primary. |
| Graph refresh | Controlled node arrays discarded measured dimensions on fresh snapshots; nodes became hidden | Run-scoped UI dimensions persist across refresh; measured layouts refit; complete Fixed/Adaptive paths stay visible. Height follows the recorded path. |
| Logs/history | Separate bounded event/activity panes plus duplicate Event History | One chronological stream with source filtering, complete details and keyboard history stepping. Distinct saved records remain labeled; no false deduplication/delivery claim. |
| Research | Configuration and trial technical data competing with results | Purpose, benchmark/mode/repetition/progress/results summary; configuration/source/check/raw JSON remain collapsed; fixture labels retained. |
| Run history | Always-expanded workspace charts and redundant run toolbar | Goal/mode/status/date/duration/final availability/actions; workspace analytics collapsed. |
| Global context | Selected Goal and run picker on unrelated pages | No selected-run context on Settings, Recycle Bin, Organizations, Agents, Research or unrelated HR. Workspace-specific stored selections and existing generation guards prevent stale tenant data. |
| Recycle Bin | Restore/delete equal prominence; protected runs could launch invalid purge dialogs | Backend-authoritative eligibility; protected status plus Restore only; eligible deletion in Danger zone with existing irreversible confirmation and atomic backend recheck. |
| HR empty state | Instruction without a clear next step | Organization-workspace availability plus workspace-selector/Organizations next step. |

## Exact contract changes and limits

All six system prompts append one shared intent/output policy. Direct now uses the
same structured prompt builder as specialists. The handoff contains:
`original_directive`, `task_type`, `stage_objective`, `relevant_sources`,
`prior_result` (source agent, output type, prior-result excerpt, excerpt flag and
explicit unverified status), `output_requirements`, and unresolved-item guidance.
The preferred predecessor order remains unchanged. Adaptive skipped outputs remain
absent. Full prior text is retained in ExecutionContext/StageExecution/messages.

Prior input is bounded to 4,000 characters, or 12,000 for report/detailed/comprehensive
requests, with a labeled omitted middle and prefix/suffix. These are mechanical,
explicitly incomplete excerpts, not invented verified facts or model summaries.
Original source bounds are unchanged and original sources remain available to final
synthesis. There is no extra provider call or new evidence store. The system does
not concatenate stage outputs as the final answer; Report synthesizes against the
original request. Models/provider token limits, Single/Fixed/Adaptive execution
semantics, Task/StageExecution/RoutePlan/GraphRunState authority and authorization
are preserved.

New runs use `prompts-v2-intent` / `contracts-v2-output`. Research configuration
hashes include the changed implementation; historical v1 records are not relabeled.
Seven benchmark definitions and research_fixtures.py were not edited. The new
browser fixture adds explicitly synthetic cases, delegating existing benchmarks to
the unchanged fixture. HR proposal schemas/roles/approval boundaries are preserved.

Final-stage format validation is optional metadata in the existing stage snapshot;
raw outputs are not rewritten. It checks recognized explicit JSON/key sets,
bullet counts/preambles, number-only answers and serialized/fenced/triple-quoted
wrappers. Safe presentation decoding is bounded. JSON scalar strings and embedded
meaningful quotes survive; explicitly requested quotation is preserved. Invalid JSON remains visible. A problem is disclosed;
no corrected model answer is fabricated. This is conservative format validation,
not a proof of semantic correctness, arbitrary JSON Schema validation or live
instruction fidelity. Violations do not masquerade as valid output, and do not
alter the fact that a provider call completed. Complete raw text remains inspectable.

Examples reproduced in regression:

| Request/case | Before | After |
| --- | --- | --- |
| Final number only | System prompts could force explanatory sections | Request contract carries answer-only; compliant fixture shows `42`; verbose numeric results are explicitly invalid. |
| Three bullets | Summarizer/report could force a differently shaped response | Same three-bullet requirement survives multiple handoffs; wrong count/preamble is invalid. |
| JSON keys x/y | Report forced plain text; quoted/fenced payload appeared literally | Required keys validated, formatted structured view; serialization/fence problems remain recorded and Raw remains exact. |
| Security risks only | Prior commentary could dominate or omit original source | Final stage receives original scope plus subordinate unverified evidence; deterministic sequence regression injects unrelated verbose commentary. Semantic live-provider behavior remains a gate. |
| Nested serialized text/newlines | Quotes/escaped newlines shown as data serialization | Clean plain reading, explicit wrapper issue, exact Raw. |
| Markdown | Literal syntax or aggressive stripping | Escaped semantic headings/lists/emphasis/code/links/tables; raw HTML and executable links are not inserted. |

## Validation

| Check | Result |
| --- | --- |
| Focused backend execution/routing/graph/storage/research regression | 202 passed, 1 restricted PostgreSQL case skipped |
| One full backend regression, justified by system execution prompt/metadata changes | 752 passed, 0 failed, 84 restricted PostgreSQL/checkpoint cases skipped; 66.16 seconds |
| Final focused review after adding safe JSON-scalar/triple-wrapper and explicitly requested quotation handling | 98 passed, 0 failed/skipped; 25.08 seconds |
| Final complete frontend | 158 passed, 0 failed, 0 skipped; 25.58 seconds |
| Frontend lint | Pass; two existing Fast Refresh mixed-export warnings |
| Frontend production build | Pass; existing large-chunk advisory, bundle about 519 kB |
| Python compileall and git diff --check | Pass |

The full backend result precedes the final narrowly tested JSON-scalar and explicit-quotation boundary
review; it was not rerun to repeat unaffected work. PostgreSQL cases were not claimed
as fresh passes. No new restricted credentials or containers were created. Earlier
Phase 10's PostgreSQL/checkpoint results remain historical evidence only.

Commands (from repository root unless noted):

```sh
PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests/test_output_consolidation.py backend/tests/test_agent_contracts.py backend/tests/test_recycle_bin.py backend/tests/test_experiment_provenance.py backend/tests/test_task_pipeline.py backend/tests/test_adaptive_routing.py backend/tests/test_graph_nodes.py backend/tests/test_fixed_graph.py backend/tests/test_adaptive_graph.py backend/tests/test_final_persistence.py backend/tests/test_research.py
PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests
PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests/test_output_consolidation.py backend/tests/test_agent_contracts.py backend/tests/test_recycle_bin.py backend/tests/test_experiment_provenance.py
npm --prefix frontend run test
npm --prefix frontend run lint
npm --prefix frontend run build
.venv/bin/python -m compileall -q backend/app backend/tests/ux_output_browser_fixture.py backend/tests/test_output_consolidation.py
git diff --check
```

## Browser and accessibility acceptance

The disposable authenticated SQLite/SDK fixture ran on ports 8019/5179. Provider
and Google calls were mocked; no paid/live requests occurred. It seeded 42 research
trials for summary inspection. The four new requests were submitted through the
actual browser form/API/engine for every mode:

| Request | Single | Fixed | Adaptive |
| --- | --- | --- | --- |
| What is 6 times 7? Give only the final number. | `42`, pass | `42`, pass | `42`, pass |
| Summarize this in 3 bullet points. Source: Cedar/Maple/Pine launch months | 3 bullets, pass | 3 bullets, pass | 3 bullets, pass |
| Return JSON with keys x and y. Set x to 1 and y to 2. | Valid x/y, pass | Valid x/y, pass | Valid x/y, pass |
| Explain only the security risks of sharing a password in a longer analysis. | 3,005-character Markdown fixture, pass | Same, pass | Same, pass |

Additional browser checks passed:

- All eight remaining top-level destinations; HR personal empty state and organization availability.
- Final Raw/Rendered switches for all twelve examples; 3,005-character copy verified in the browser clipboard.
- Verbose 12,760-character intermediate/handoff previews, explicit expansion and exact full Raw access; selected-stage output remains secondary to Final answer.
- Events source filter; Home key sets history position to one record; contextual Inspect record focuses the inspector heading.
- Fixed graph's eight nodes and Adaptive graph's six nodes visibly persist after run/telemetry changes; recorded route/path/handoff evidence remains available.
- History's final availability and collapsed analytics; removed run picker/selected goal on unrelated destinations.
- Reversible removal dialog Escape/cancel, move-to-bin, protected status, zero permanent-delete buttons, restore back to history.
- Organization Research summary: purpose, three modes, seven benchmarks, two repetitions, 42/42 progress; advanced details initially closed.
- Switching Personal → organization → empty IAM-only workspace hides the previous run; returning to Personal scopes selection correctly.
- Focus reading uses a native modal; initial focus on close, backward Tab containment, Escape dismissal and return to the trigger verified. Keyboard Enter changes detail views and expands output. Existing reduced-motion CSS was reviewed and preserved, not dynamically emulated.
- CSS viewport widths 400, 768 and 1548: document width matches viewport, no horizontal page overflow. Mobile nav targets measured about 45 CSS pixels. Temporary viewport overrides reset.

Eligible destructive deletion retains backend confirmation/retention regression;
no permanent UI purge was performed. This browser acceptance establishes plumbing,
evidence access and presentation, not live model response quality or production
security acceptance. The fixture servers were stopped after acceptance.

## Preserved advanced evidence and remaining gates

Technical IDs, original directive, raw provider text, original source context,
stage durations/tokens/models, route reasons/selected/skipped stages, complete saved
messages/events/activity, research fingerprints/configuration/checks/limitations,
independent human rubric history and exports remain accessible. Task is authoritative;
graph measurement state is local UI geometry, not duplicate persisted execution.

Fresh restricted PostgreSQL/checkpoint acceptance, approved live-provider fidelity
and controlled research, production tenancy/proxy/OAuth/restart checks, and the
academic report/PPT remain gates. No claim of trained models, global superiority,
significance or production readiness is made. Local acceptance ends here.

Screenshots: [focused reading](ux-output-evidence/focused-output.jpg),
[Live/output](ux-output-evidence/live-output.jpg),
[mobile](ux-output-evidence/mobile-live.jpg).

## Changed files

- `README.md`
- `backend/README.md`
- `backend/app/agents/analysis_agent.py`
- `backend/app/agents/base_agent.py`
- `backend/app/agents/contracts.py`
- `backend/app/agents/data_agent.py`
- `backend/app/agents/direct_agent.py`
- `backend/app/agents/output_contract.py`
- `backend/app/agents/report_agent.py`
- `backend/app/agents/research_agent.py`
- `backend/app/agents/summarizer_agent.py`
- `backend/app/experiments/provenance.py`
- `backend/app/models/schemas.py`
- `backend/app/storage/database.py`
- `backend/tests/test_agent_contracts.py`
- `backend/tests/test_experiment_provenance.py`
- `backend/tests/test_output_consolidation.py`
- `backend/tests/test_recycle_bin.py`
- `backend/tests/test_task_pipeline.py`
- `backend/tests/ux_output_browser_fixture.py`
- `docs/FINAL_DEMO_GUIDE.md`
- `docs/FINAL_PROJECT_GUIDE.md`
- `docs/PROJECT_STATE.md`
- `docs/UX_OUTPUT_CONSOLIDATION_ACCEPTANCE.md`
- `docs/ux-output-evidence/focused-output.jpg`
- `docs/ux-output-evidence/live-output.jpg`
- `docs/ux-output-evidence/mobile-live.jpg`
- `frontend/src/App.jsx`
- `frontend/src/components/dashboard/AgentRelationshipGraph.jsx`
- `frontend/src/components/dashboard/OutputViewer.css`
- `frontend/src/components/dashboard/OutputViewer.jsx`
- `frontend/src/components/dashboard/SimulationDetails.jsx`
- `frontend/src/components/dashboard/TaskDetailsPanel.jsx`
- `frontend/src/components/dashboard/WorkspaceInspector.jsx`
- `frontend/src/components/dashboard/WorkspaceShell.css`
- `frontend/src/context/SimulationContext.jsx`
- `frontend/src/layout/AppShell.css`
- `frontend/src/layout/Sidebar.jsx`
- `frontend/src/layout/Topbar.jsx`
- `frontend/src/pages/Hiring.jsx`
- `frontend/src/pages/Logs.jsx`
- `frontend/src/pages/Messages.jsx`
- `frontend/src/pages/RecycleBin.jsx`
- `frontend/src/pages/ResearchLab.jsx`
- `frontend/src/pages/Settings.jsx`
- `frontend/src/pages/TaskSummary.jsx`
- `frontend/src/utils/graphPresentation.js`
- `frontend/src/utils/outputPresentation.js`
- `frontend/src/utils/recycleBin.js`
- `frontend/tests/graphPresentation.test.js`
- `frontend/tests/output-consolidation.test.js`
- `frontend/tests/research.test.js`
