# AI Agent Environment Simulator: A Multi-Agent AI Platform for HR Analytics

AI-Agent-Environment-Simulator is an academic React/Vite and FastAPI application for observing persisted
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

Use Python **3.13** (validated locally with 3.13.3). Python 3.10+ satisfies the
current declared minimums, but other interpreter versions have not been freshly
validated. Use Node **22.12+ on the 22.x line**, or another supported Node release
satisfying Vite's `^20.19.0 || >=22.12.0` requirement. Existing acceptance used
Node 25.5.0. Check `python3 --version`, `node --version` and `npm --version` first.

Clone the repository, or obtain the agreed review branch after it is published:

```sh
git clone https://github.com/shreetejshinde2003/AI-Agent-Environment-Simulator.git
cd AI-Agent-Environment-Simulator
```

### Backend terminal

For a fresh checkout, create a virtual environment at the repository root, then
run the backend from `backend/` so settings and SQLite resolve consistently:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend
cp .env.example .env
# Configure the private development settings described below before sign-in.
python run.py
```

Copy the template only when `.env` does not already exist; preserve existing private
settings. `python run.py` serves the API at `http://localhost:8000`. The alternative
is `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` from
`backend/`. Use one API worker. All settings are declared in `app/core/config.py`;
process environment overrides the working-directory `.env`.

The template explicitly selects `DATABASE_URL=sqlite:///./simulator.db`, which
creates/initializes **backend/simulator.db** during startup. No separate database
server or manual migration command is required for a fresh local SQLite database.
Starting from another directory selects a different relative database and `.env`.
Initialization can upgrade existing databases: back up an existing database before
starting newer code. Never use production PostgreSQL credentials for development.
Leave checkpoint, graph-runtime and live-research flags at their template defaults.

### Frontend terminal

From the repository root in a second terminal:

```sh
cd frontend
npm ci
cp .env.example .env
npm run dev -- --port 5173 --strictPort
```

Again, do not overwrite an existing `.env`. Open **http://localhost:5173**.
Frontend installation, tests, lint, build, login-page rendering and `/privacy` or
`/terms` rendering require no production credentials. The authenticated workspace
requires real Google development sign-in; demo mode does not bypass authentication.
Use `npm run dev` for local API work: `npm run preview` uses production-origin auth
routing and has no local backend proxy.

Development API requests go directly to `http://localhost:8000`; Vite does not
proxy them. `VITE_API_BASE_URL` selects REST and development auth/workspace traffic;
`VITE_WS_URL` selects `/ws/live`. These browser-visible variables must never contain
credentials. Ollama is not used by the current runtime and need not be started.

### Google development sign-in

An authorized Google OAuth **Web application** development client is required.
GitHub collaborator access and cloning do not supply OAuth client credentials.
Obtain a dedicated development client through the project owner or an authorized
Google Cloud project administrator; do not reuse production secrets.

Set these privately in `backend/.env`:

| Variable | Local configuration |
| --- | --- |
| `GOOGLE_CLIENT_ID` | Authorized development client ID; blank in the template. |
| `GOOGLE_CLIENT_SECRET` | Development client secret; blank in the template. |
| `GOOGLE_REDIRECT_URI` | `http://localhost:8000/api/v1/auth/google/callback` |
| `FRONTEND_URL` | `http://localhost:5173` |
| `CORS_ORIGINS` | JSON list of trusted local frontend origins; supplied in the template. |

In Google Cloud Console, register the exact callback above as an **Authorized
redirect URI** for that development web client. Configure the OAuth consent screen
and permitted/test users as appropriate to the project's publishing status and
account restrictions. If configuring Authorized JavaScript origins, use the local
frontend origin `http://localhost:5173`; it is not a replacement for callback
registration. Use `localhost` consistently through frontend, API and callback.
Restart the backend after changing settings; restart Vite after changing its `.env`.

`GROQ_API_KEY` is optional for frontend/manual-record work. Actual AI execution
requires a valid separately authorized development Groq credential and provider
access. Missing credentials must surface errors; never disable authentication or
create fake application sessions to work around setup.

### Connection diagnostics

- Open `http://localhost:8000/health`: expect HTTP 200 with `status: ok`.
- Before sign-in, `/api/v1/auth/me` returns **401**, which the frontend treats as
  anonymous. Protected workspace APIs also require authentication.
- `/api/v1/auth/google/login` returns **503 / google_auth_not_configured** if any
  of the four required OAuth settings is blank. Check names/presence, backend
  working directory and process overrides without printing secret values.
- With configuration present, login starts with a **302** to Google. A redirect
  mismatch means the configured callback must match the development client's
  registered URI exactly; configuration presence does not prove valid credentials.
- If Vite cannot start, check the Node requirement and dependency installation.
  `--strictPort` makes an occupied 5173 fail explicitly instead of changing origins.
- In browser Network/Console, verify requests target the local API, not Vercel or
  Railway. For CORS/403 errors, check `CORS_ORIGINS`, `FRONTEND_URL`, actual browser
  origin and consistent hostname/ports. Do not share cookies or authorization headers.
- For WebSocket failures, verify `ws://localhost:8000/ws/live`, successful sign-in
  and workspace selection. REST refresh remains available when the live socket fails.

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
