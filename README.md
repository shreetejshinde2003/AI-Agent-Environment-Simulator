# AI-Agent-Environment-Simulator

An existing React/Vite + FastAPI application for observing real multi-agent execution.
Originally focused on HR analytics, the V1 workspace also accepts general directives.
LLM responses are generated through the existing server-side Groq client.

## What works

Create a simulation, optionally attach TXT/CSV/JSON reference data, and run:

```text
Original goal → Sequential coordinator → Research → Data → Analysis → Summarizer → Report
                                         findings   records   insights    summary    final output
```

Every stage receives the original goal. Each output becomes the next agent's context.
The same five agents can also execute individually. The coordinator remains in
`backend/app/api/routes/tasks.py`; LangGraph is not a runtime dependency.

The workspace shows a live React Flow graph, stage details, handoffs, timestamped
events, real metrics/charts, final results, saved history, and TXT/JSON/CSV exports.
No execution data is seeded or silently replaced with a demo. Missing measurements
are labeled as unavailable.

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

## Storage and safety

SQLite schema version 1 stores simulations with nested stage executions, messages,
events, activities, results, metrics and upload metadata/prepared context. Startup
initializes the schema idempotently. Interrupted runs are marked failed after a
restart; they are never silently retried or marked successful.

This is a **shared, unauthenticated workspace**, not a private multi-user service.
The nullable owner field is an extension point, not authorization. Do not upload
secrets or sensitive personal/HR data. Uploaded context is sent to Groq during
execution. Only bounded prepared context is retained; original file bytes are not
an archival upload facility.

Use one API worker for this local V1. Multiple workers, durable distributed jobs,
pagination and retention policies are later hardening work. On Railway, an
ephemeral filesystem cannot guarantee history across deployments: durable storage
must be provisioned before relying on production persistence. No deployment
configuration is changed by this milestone.

## Validation

```bash
python -m compileall backend/app
(cd backend && python -m unittest discover -s tests -v)
npm --prefix frontend run lint
npm --prefix frontend run build
git diff --check
```

Automated tests mock providers and use temporary databases; they consume no Groq
credits. See [V1 audit and validation](docs/V1_AUDIT.md) for the audit matrix,
limits, schema/API changes, and real integration results.

## Not implemented

Web Search, PDF extraction, authentication, custom executable agents,
pause/cancel of active model requests, and automatic retry/resume remain unavailable.
Event History inspects recorded events; it does not pretend to replay execution.
The old `agents/orchestrator.py` LangGraph prototype and unused frontend demo
fixtures remain reference code only, outside the active runtime.

## Repository and team

- `frontend/src/`: workspace pages, dashboard components, hooks and API client.
- `backend/app/`: FastAPI routes, schemas, agents and SQLite repository.
- `backend/tests/`: mocked backend regression tests.
- `database/`: project datasets; never loaded into prompts automatically.

Shreetej Shinde leads backend, agents, integration and repository management.
Sumit Jadhav works on datasets and database documentation. Parag Kulkarni works
on frontend, UI/UX and visualization. This remains an academic project; license
selection is pending.
