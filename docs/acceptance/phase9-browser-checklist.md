# Phase 9 browser acceptance — 7 October 2026, Asia/Kolkata

20 checkpoints passed, 0 remaining failed, 0 skipped. These are manual UI
checkpoints, separate from automated test counts. Real React/Vite on 127.0.0.1:5179
and authenticated FastAPI on 127.0.0.1:8019, disposable SQLite, synthetic sessions,
and SDK-boundary deterministic fixtures. No live provider or Google login.

| # | Checkpoint | Result |
| --- | --- | --- |
| 1 | Empty workspace has explicit no-experiment/no-metrics state and disabled start without cases | Pass |
| 2 | Benchmark detail reveals actual ID/version/directive/source/checks | Pass |
| 3 | Mode checkbox selection changes native checked state | Pass |
| 4 | Two repetitions across all modes shows six planned runs | Pass |
| 5 | Admission disables configuration/actions while awaiting acknowledgement | Pass |
| 6 | Six persisted trials become completed records in experiment history | Pass |
| 7 | Case/mode table shows measured latency/tokens/starts/handoffs and n/range/SD | Pass |
| 8 | Missing human scores display Unknown with n=0 | Pass |
| 9 | Adaptive trial reveals research/report selection and three skipped specialists | Pass |
| 10 | Seven rubric entries and rationale persist with actor/time/output digest | Pass |
| 11 | Reload results retains saved assessment and updates human-score n | Pass |
| 12 | Review history reveals original source and saved notes | Pass |
| 13 | Open run evidence reaches the existing graph/inspector; final build labels fixture evidence | Pass |
| 14 | Rerun produces a new six-run experiment with completed fixture trials | Pass |
| 15 | Controlled failed trials show 0% success and unknown/unavailable tokens | Pass |
| 16 | Fixed failure preserves failed Research and four unexecuted downstream stages; no successful output/scoring form | Pass |
| 17 | Workspace switch clears comparison/trial/output/review data and shows separate empty history | Pass |
| 18 | Final backend build admits/completes a separate three-mode organization experiment | Pass |
| 19 | Export presents complete API report JSON with evidence, interpretation, conclusion and reproduce metadata | Pass |
| 20 | Seven cases × three modes × five trials shows 105 planned runs and disables admission above 45 | Pass |

A saved rubric score was entered only to exercise UI persistence. Its note says
“Fixture UI acceptance score only; source matches glossary. Not an independent
research judgment.” It is not included in the 42-trial research acceptance report
as an independent human assessment.

During acceptance, an in-app browser download event was unavailable for the JSON
blob export. A full read-only report preview was added and verified against the
real report API. The preview permits selection/copy; a saved browser download is
not claimed. Development server restarts and hot reload reset transient selections;
reselecting saved records retrieved their persisted evidence. An inaccessible
Playwright selector was replaced with native keyboard selection. Final source was
reloaded after the export change; no live provider traffic was used to recover.

Screenshots: `../screenshots/phase9-comparison.jpg`, `phase9-failure.jpg`,
`phase9-report.jpg`. Initial narrow browser layout was visually exercised; no
numeric responsive-width assertion is claimed. No viewport override was retained.
Both fixture servers and the disposable database are removed after acceptance.
