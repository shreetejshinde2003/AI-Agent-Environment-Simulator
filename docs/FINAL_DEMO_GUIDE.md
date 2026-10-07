# Academic demonstration and technical summary

## Demonstration scope

Present FMProject as an inspectable orchestration and tenant-secure human HR workflow.
Use synthetic material. State before showing metrics: **these are deterministic
local fixture results; they validate machinery, not live model superiority**.
The [final acceptance report](PHASE10_ACCEPTANCE_REPORT.md) and
[current architecture](FINAL_PROJECT_GUIDE.md) define the actual delivered scope.

## Repeatable offline fixture

From the repository root, using the existing dependencies, open two terminals:

```sh
.venv/bin/python backend/tests/ux_output_browser_fixture.py
```

```sh
VITE_API_BASE_URL=http://127.0.0.1:8019 npm --prefix frontend run dev -- --host 127.0.0.1 --port 5179 --strictPort
```

Open `http://127.0.0.1:8019/_local_browser_fixture/recruiter`.
This explicit test-only endpoint establishes a disposable authenticated session and
redirects to the local UI. Its test database is outside application data, contains
synthetic HR sources, and seeds seven cases × three modes × two repetitions.
The SDK is mocked before admission. No real Google/Groq call occurs. No production
flag, .env or user/application database is modified. Never deploy this fixture.

The same test-only endpoint supports `reviewer`, `approver`, `combined`, `iamadmin`
and `member`. Changing that final path switches synthetic test sessions; all
subsequent UI actions use actual authenticated application APIs and persistence.
Each role also has an IAM-only organization for exclusion checks.
Stop both terminals with Ctrl-C after the demo; normal fixture teardown disposes
its database. Browser screenshots/entered rubric scores remain demonstration
acceptance, not independent research evaluation.

For a file-based repeat without a UI, preserve earlier evidence with a new output:

```sh
.venv/bin/python backend/scripts/research_acceptance.py --output /private/tmp/fmproject-demo-report.json
```

The command uses disposable SQLite, actual API/engine and mocked SDK output.
Remove the synthetic temporary report when it is no longer needed. Actual local
PostgreSQL enforcement is a separate approved acceptance workflow, not a demo-login
prerequisite.

## Concise presentation flow (about 12–15 minutes)

| Time | Show | Explain |
| --- | --- | --- |
| 1 minute | Objective and architecture | The contribution is persistent inspectable execution plus controlled comparison and authorized human workflow; no model was trained. |
| 2 minutes | Same glossary input in Single/Fixed/Adaptive | Single has Direct/no handoffs; Fixed has five specialists/four handoffs; Adaptive records selected/skipped agents and rule reasons. The coordinator/router makes no model request. |
| 1 minute | Inspector, events, failure and recycle/restore | Task/stage evidence survives; a failed stage leaves honest failure and unstarted downstream stages. The Events view includes recorded history stepping. Restore retains execution evidence. |
| 1 minute | Custom Agent Builder | Save a bounded text definition/revision, run it and inspect the original configuration fingerprint/output. No tools/scripts/credentials are configurable. |
| 2 minutes | Research Lab's 42 fixture trials and JSON report | Show matching inputs/configuration, repetitions, sample counts, route avoidance, coverage and unknown cost/human quality. Fewer stages alone does not establish better reasoning. |
| 3 minutes | Organization requirement/knowledge → human JD → AI proposal | Select exact source revisions, explicitly author/save the JD and run assistance separately. AI output is only a proposal and never overwrites the saved human draft. |
| 2 minutes | Distinct Reviewer/Approver sessions | Recruiter submits; Reviewer requests changes; Recruiter revises/resubmits; Reviewer recommends; Approver explicitly confirms. Show authenticated history and exact revision. |
| 1 minute | Newer revision and permission denial | Earlier approval remains on its old revision. Personal/IAM-only workspaces cannot acquire HR authority. |
| 1 minute | Acceptance and limitations | Cite exact final test counts. Production proxy/role/OAuth/restart/live-provider gates remain unverified; there is no global winner or statistical inference. |

Useful synthetic input:

```text
Expand RTO using the glossary.

Source:
Glossary: RTO means recovery time objective.
```

For an Adaptive analysis example, select the explicit `analysis` category and use
source-bound plan arithmetic. For the known failure fixture, use the directive
`Phase10 provider failure`. The fixture deliberately rejects it; no provider outage
is implied. Save human-review notes that explicitly say they are fixture acceptance.

## Output/intent demonstration

This fixture adds four synthetic request cases without editing the seven benchmark
fixtures. Execute each in Single, Fixed and Adaptive:

- `What is 6 times 7? Give only the final number.` → `42`.
- `Summarize this in 3 bullet points.` followed by a new line
  `Source: Cedar launches in May. Maple launches in June. Pine launches in July.`
  → exactly three bullets.
- `Return JSON with keys x and y. Set x to 1 and y to 2.` → `{"x":1,"y":2}`.
- `Explain only the security risks of sharing a password in a longer analysis.`
  → a longer Markdown security-risk fixture for reading/overflow checks.

The SDK mock deliberately supplies verbose unrelated intermediate commentary.
Open Handoffs to expand the complete persisted response; then read Final answer
and switch Raw/Rendered. This verifies original-request/contract plumbing and UI
behavior, not real model robustness. Show the focused reading dialog, copy, Escape
and returned focus. Open Events to filter one chronology and step through records.
Move a completed synthetic run to Recycle Bin and show Restore plus evidence
protection, with no permanent-delete control. No live provider call is needed.

Main navigation has eight task destinations; execution detail belongs to Live
Simulation. Show Research Lab's collapsed configuration and fixture label before
explaining metrics. Use current counts from PROJECT_STATE.md; the Phase 10 report
retains its original counts and date. Production, fresh restricted PostgreSQL and
live-provider quality checks remain separate gates.

## What was actually built

FMProject is a full-stack academic AI orchestration application with persistent
Task/stage/route evidence, genuinely distinct Single/Fixed/Adaptive paths,
versioned deterministic routing, and an optional integrated LangGraph checkpoint
runtime. Google OIDC and opaque revocable sessions authorize private workspaces
and organization IAM. PostgreSQL FORCE RLS protects tenant records under trusted
transaction context. Bounded custom agents retain immutable configuration revisions.

The HR workflow persists requirements, organization knowledge and human JD
revisions. Specialized Groq agents produce validated proposals in existing execution
evidence. Recruiter/Reviewer/Approver roles drive explicit revision-pinned immutable
human decisions. Research Lab retains controlled synthetic benchmarks, repetitions,
configuration/source fingerprints, descriptive metrics, independent human rubric
history and reproducible evidence exports. Phase 10 adds reproduced migration,
frontend stale-response and research-integrity fixes, consolidated regression,
real local PostgreSQL/recovery acceptance and final documentation.

This summary supports the final report, PPT, viva, README or resume without implying
trained models, live comparative gains or a released production system.

## Viva answers and claims to keep precise

- **Why both checkpoint and Task storage?** Checkpoints retain orchestration cursor;
  Task/StageExecution remain authoritative business lifecycle and evidence.
- **What is Adaptive?** A rules-v1 capability route using validated input; no learned
  or LLM router, no silent fallback or skipped-artifact fabrication.
- **Can AI approve a JD?** No. Human authoring and explicit authorized decisions own
  records; approval binds only the submitted revision.
- **What did the experiment prove?** Local machinery acceptance and differing
  topology. Fixture outputs/usage are controlled, timings include local overhead,
  and no live-provider superiority or significance was established.
- **Is RLS sufficient against credential theft?** No. It assumes trusted service
  context and protected credentials; SQLite additionally depends on API checks.
- **Is external execution exactly once?** No. A crash before committing successful
  provider output may repeat the request on explicit recovery.
- **Is it production-ready?** Local acceptance passes; the documented production
  gates require independent authorization and environment-specific verification.
