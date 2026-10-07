# FMProject — Multi-Agent AI Environment Simulator

FMProject is an academic React/Vite and FastAPI application for observing persisted
AI execution, comparing Single / Fixed / Adaptive orchestration, and assisting
organization HR teams with revision-bound proposals and explicit human review.
It uses the central Groq adapter; Google supplies identity through OIDC, not AI.

Phase 10 final local acceptance is documented in
[the consolidated report](docs/PHASE10_ACCEPTANCE_REPORT.md).
The current [release-candidate state](docs/PROJECT_STATE.md) and
[UX/output consolidation acceptance](docs/UX_OUTPUT_CONSOLIDATION_ACCEPTANCE.md)
record subsequent local work without adding a feature phase.
Local acceptance and production acceptance are separate. Live-provider research,
production tenancy, proxy/cookie topology and graph activation remain release gates.
No experiment establishes a globally superior mode or statistical significance.

## What was built

| Area | Current behavior |
| --- | --- |
| Simulation | Create a run with bounded TXT/CSV/JSON context; inspect saved stages, handoffs, events, measurements and final output; export terminal runs. |
| Single | One neutral Direct Agent stage, without specialist handoffs. |
| Fixed | Research → Data → Analysis → Summarizer → Report; five specialist stages. |
| Adaptive | Versioned deterministic capability rules choose a validated specialist route. Selected/skipped agents and reasons are retained. No model-based router. |
| LangGraph | Integrated graphs reuse the shared Task/stage lifecycle and separate restricted PostgreSQL checkpoints. Disabled by default; explicit authenticated resume is available only when configured. |
| Identity and tenancy | Google OIDC; opaque revocable sessions; private Personal Workspaces; active Organization memberships with Owner/Admin/Member IAM. |
| Agent Builder | Bounded, workspace-owned text agents; immutable saved configuration revisions; manager authoring and member execution. |
| HR Hiring | Persistent requirements, organization role knowledge, human JD drafts, immutable revisions and exact source links. Personal Workspaces have no organization HR semantics. |
| HR assistance | Requirement assessment, JD proposals and saved-draft validation through Groq. Task/StageExecution retain original evidence; AI never overwrites human records. |
| Human review | Recruiter submission, Reviewer recommendation/change request, Approver approval/rejection; decisions apply only to the exact submitted revision. IAM roles alone grant no HR authority. |
| Research Lab | Seven versioned synthetic benchmarks, controlled modes/repetitions, per-case descriptive comparisons, independent human rubric history, rerun provenance and evidence export. |
| Recycle Bin | Soft-delete and restore complete simulation records; owner-only purge is blocked when execution evidence must be retained. |

Navigation now centers on Live Simulation, Simulation History, Research Lab, Agents,
HR Hiring, Organizations, Recycle Bin and Settings. Handoffs/events/history stepping
are contextual run views. Final answers have full-width Rendered/Raw/copy/focused
reading; technical evidence and workspace metrics remain collapsed and accessible.

Task is the authoritative run lifecycle/evidence record. StageExecution owns stage
evidence; RoutePlan owns Adaptive selection. LangGraph checkpoint state stores
orchestration progress. REST is authoritative after WebSocket reconnect.

See the current [project/architecture guide](docs/FINAL_PROJECT_GUIDE.md),
[security and release assessment](docs/RELEASE_READINESS.md), and
[academic demo and technical summary](docs/FINAL_DEMO_GUIDE.md).
Historical phase reports remain evidence of their own checkout and date.

## Local development

The accepted environment uses the existing root `.venv`, Python 3.13.3 and Node 25.5.0.
For a fresh checkout, install the backend requirements into a virtual environment:

```sh
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Configure settings privately through environment variables or the `.env` in the
backend process's working directory. All application settings live in
`backend/app/core/config.py`. Supply Google OAuth client/secret, exact callback URL,
frontend origin and trusted CORS origins to use real sign-in; supply a Groq key to
run real AI. Never commit credentials or put provider keys in frontend variables.
Missing configuration produces explicit errors. From `backend/`, copy
`.env.example` to `.env` and supply only the settings needed for your environment.

```sh
cd frontend
npm install
npm run dev
```

Vite defaults to 5173 and the API to 8000. Set `VITE_API_BASE_URL` for the actual API
origin and optionally `VITE_WS_URL` for `/ws/live`. Backend/.env loading and the
relative `sqlite:///./simulator.db` path depend on the backend working directory;
starting from the repository root selects a different database from starting in
`backend/`. Choose the intended database explicitly. Use one API worker.

For an offline, disposable academic demonstration using synthetic inputs and
mocked provider responses, follow [the demo fixture instructions](docs/FINAL_DEMO_GUIDE.md).
That fixture is test infrastructure and never part of the deployed API.

## Persistence and data

Operational schema remains **13**. SQLite provides local storage; `DATABASE_URL`
selects PostgreSQL. Initialization installs ENABLE/FORCE RLS on **22 tenant-owned
PostgreSQL tables**. Identities/sessions and system-global metadata have separate
trusted-service access assumptions. Production database role and migration checks
are described in the release assessment.

V1 SQLite migrations preserve archive tables and a separate backup; additive
upgrades preserve execution, HR and human-decision history. Restart marks interrupted
runs failed; it never silently repeats a provider call or invents success. Configured
LangGraph resume reconciles checkpoints with committed evidence. Exactly-once
external provider calls are not promised.

Six privately provisioned employee/HR JSON datasets are benchmark inputs, separate
from the operational database. Place them under `data/benchmark/` or set
`BENCHMARK_DATA_DIR`; register from `backend/` with `python -m app.datasets.cli register`.
Only bounded non-personal aggregates enter dataset-based prompts. User-uploaded
context and selected HR sources are sent to Groq during AI execution and are not
automatically anonymized. Use synthetic demonstration material.

Research benchmarks are committed separately at `database/benchmarks/research-v1.json`.
Fixture acceptance measures orchestration, persistence and measurement machinery.
Fixture token values are controlled; fixture latency includes local overhead and
has no live-provider/network component. Missing usage/cost stays unknown. Surface
checks and human rubric assessments are separate. No live quality, pricing, speed,
significance or superiority claim follows from fixture acceptance.

## Validation

From the repository root with the existing `.venv`:

```sh
.venv/bin/python -m pytest backend/tests
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
.venv/bin/python -m compileall -q backend/app backend/tests backend/scripts
.venv/bin/python -m pip check
git diff --check
```

Providers are mocked in tests. Real local PostgreSQL tests require explicitly
approved restricted credentials and isolated schemas; absent credentials cause
skips, not verified enforcement. Run expensive suites serially on an 8 GB machine.
The [final report](docs/PHASE10_ACCEPTANCE_REPORT.md) records exact counts and cleanup.

## Limits and release gates

Web Search, PDF extraction, arbitrary tools/scripts, autonomous HR decisions,
publication, automatic retries, user-requested pause/cancel of model calls, a durable
job queue and coordinated multi-worker startup are unavailable. Event History
steps through recorded events; it does not replay execution. The inactive legacy
`agents/orchestrator.py` prototype and frontend demo fixtures are outside the active
application runtime.

The documented deployment target is Vercel → Railway FastAPI → PostgreSQL.
Checked-in Vercel routing proxies authentication only, while production workspace
requests use the frontend origin. That topology requires an explicitly authorized
configuration change and deployed verification. No production configuration,
provider credentials, graph activation, push or deployment is part of Phase 10.

## Repository and team

- `frontend/src/`: pages, reusable controls, execution views, hooks and API clients.
- `backend/app/`: routes, request models, agents, security and persistence.
- `backend/tests/`, `frontend/tests/`: regression and explicit test-only fixtures.
- `docs/`: architecture, phase reports, final guides and acceptance evidence.
- `data/benchmark/`: privately provisioned domain datasets.
- `database/benchmarks/`: versioned synthetic research definitions.

Shreetej Shinde leads backend, agents, integration and repository management;
Sumit Jadhav works on datasets and database documentation; Parag Kulkarni works on
frontend, UI/UX and visualization. License selection remains pending.
