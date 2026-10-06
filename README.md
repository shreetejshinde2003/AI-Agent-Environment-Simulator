# AI-Agent-Environment-Simulator

An existing React/Vite + FastAPI application for observing real multi-agent execution.
Originally focused on HR analytics, the V1 workspace also accepts general directives.
LLM responses are generated through the existing server-side Groq client.

## What works

Create a simulation, optionally attach TXT/CSV/JSON reference data, and choose
`fixed` (default), `single`, or rule-based `adaptive`:

```text
Original goal → Sequential coordinator → Research → Data → Analysis → Summarizer → Report
                                         findings   records   insights    summary    final output
```

Every stage receives the original goal. Each output becomes the next agent's context.
The direct-answer `single` baseline makes one model call with the same bounded
permitted input and records one stage, without handoffs. The five specialist
agents can still execute individually through legacy `single_agent` mode; that
is not the research baseline. `adaptive` selects specialist capabilities using
versioned deterministic rules, validates their input contracts, and executes only
that route. No routing model call is made. Selected/skipped agents and concise
reasons are saved and displayed; this is not learned or LLM-based routing.
The coordinator remains in
`backend/app/api/routes/tasks.py`; LangGraph is not a runtime dependency.

The workspace shows a live React Flow graph, stage details, handoffs, timestamped
events, real metrics/charts, final results, saved history, and TXT/JSON/CSV exports.
No execution data is seeded or silently replaced with a demo. Missing measurements
are labeled as unavailable.
New runs open automatically. A searchable run picker uses deterministic directive
excerpts as titles; immutable IDs remain in details/API/exports. Adaptive graphs
show only selected stages, not the skipped five-agent chain.

## Local development

Use Python 3.10+ with the pinned backend requirements (validation used Python 3.13).

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Configure your existing backend/.env securely; never commit credentials.
python run.py
```

Start from `backend/`: settings resolve the local `.env` and SQLite path relative
to the working directory. Keep the existing Groq key/model configuration.
The browser never receives provider credentials.

```bash
cd frontend
npm install
npm run dev
```

Vite defaults to port 5173; the API defaults to 8000. Set the frontend build's
`VITE_API_BASE_URL` to the backend origin. WebSocket uses that origin with
`ws/wss` and `/ws/live`, unless `VITE_WS_URL` is provided. A production build
does not default to localhost.

## Storage and benchmark data

The version 2 operational schema stores simulations, one task per simulation,
stage executions, handoffs, events, metrics, uploads, dataset metadata and the
agent roster. SQLite remains the local fallback when `DATABASE_URL` is absent;
a PostgreSQL URL selects PostgreSQL for Railway. Startup initializes schema
version 2. Existing V1 SQLite records are validated, backed up and migrated
without deleting the original tables. Interrupted runs are marked failed after
a restart; they are never silently retried or marked successful.
The existing `execution_mode` string column and run snapshot store Phase 3.1
mode values without a schema change; old `full_pipeline` records read as `fixed`.

The six `employee_*` and `hr_*` JSON files are **benchmark/domain inputs**, not
the operational database. For local benchmark use, place them under
`data/benchmark/` (or private `BENCHMARK_DATA_DIR`); they are excluded from Git, validated and registered with
`(cd backend && python -m app.datasets.cli register)`. Raw records stay on disk;
only metadata and bounded non-personal aggregates enter the application.
See [dataset audit](docs/PHASE2_DATASET_AUDIT.md) and
[database/deployment guide](docs/PHASE2_DATABASE_DEPLOYMENT.md).

This is a **shared, unauthenticated workspace**, not a private multi-user service.
The nullable owner field is an extension point, not authorization. Do not upload
secrets or sensitive personal/HR data. Uploaded context is sent to Groq during
execution. Only bounded prepared context is retained; original file bytes are not
an archival upload facility.

Use one API worker: execution remains in-process, and multiple workers are not
coordinated. Production uses Vercel → Railway FastAPI → Railway PostgreSQL.
On 2026-09-29, a real five-agent run from commit `ef27951` remained in Simulation
History with its result and execution details after a backend restart. This
verifies operational persistence across backend restarts, not loss of the
PostgreSQL service. Production provisioning of the benchmark JSON files remains
unverified; they are separate from operational storage. See the
[production verification](docs/PHASE2_DATABASE_DEPLOYMENT.md#production-verification--2026-09-29).

## Validation

```bash
python -m compileall backend/app
python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
git diff --check
```

Automated tests mock providers and use temporary databases; they consume no Groq
credits. See [V1 audit and validation](docs/V1_AUDIT.md) for the audit matrix,
limits, schema/API changes, and real integration results.

## Executable Agent Builder (Phase 4.9)

The Agents page supports tenant-owned, revisioned text agents with validated
configuration, owner/admin management and member execution. Runs use the existing
Groq adapter and persist real Task/StageExecution evidence. Schema 11 is additive;
new PostgreSQL tables use FORCE RLS. See [Agent Builder behavior and local
acceptance](docs/PHASE4_AGENT_BUILDER.md) for APIs, security boundaries and gates.

## Not implemented

Web Search, PDF extraction, user-requested pause/cancel of active model requests,
automatic retry, arbitrary agent tools and LLM-based routing remain unavailable.
Authentication, workspace IAM, evaluation, recycle bin and bounded custom agents
are implemented locally. The LangGraph runtime has passed local acceptance but
remains disabled by default pending its documented deployment gates. Custom agents
use a separate one-stage path and cannot resume through LangGraph.
Production verification remains a separate deployment gate. No comparative study
has established superiority over Single or Fixed.
Event History inspects recorded events; it does not pretend to replay execution.
The old `agents/orchestrator.py` LangGraph prototype and unused frontend demo
fixtures remain reference code only, outside the active runtime.

## Repository and team

- `frontend/src/`: workspace pages, dashboard components, hooks and API client.
- `backend/app/`: FastAPI routes, schemas, agents and relational repository.
- `backend/tests/`: mocked backend regression tests.
- `data/benchmark/`: privately provisioned validated benchmark JSON files.

Shreetej Shinde leads backend, agents, integration and repository management.
Sumit Jadhav works on datasets and database documentation. Parag Kulkarni works
on frontend, UI/UX and visualization. This remains an academic project; license
selection is pending.
