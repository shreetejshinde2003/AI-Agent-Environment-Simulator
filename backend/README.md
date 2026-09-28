# FastAPI backend

The V1 engine is the existing sequential coordinator in `app/api/routes/tasks.py`.
It uses FastAPI BackgroundTasks and the existing Groq client, not LangGraph.
Phase 3.1 adds `single` (one neutral Direct Agent call) and names the existing
five-agent pipeline `fixed`; `adaptive` returns HTTP 501 until implemented.

## Run and validate

Run from this directory so existing `.env` loading and relative SQLite paths work:

```bash
python run.py
python -m pytest -q
python -m compileall app
```

Install `requirements.txt` into a virtual environment first. Configure credentials
privately; never print or commit their values. Tests mock agents/providers and use
temporary databases. No provider credits are required.

## Contracts

Python fields are snake_case; `CamelModel` serializes REST/WebSocket JSON camelCase.
Legacy `/api/v1/tasks` retains `queued/in_progress/completed/failed`. A missing
mode on that legacy endpoint still selects one specialist; `/simulations` defaults
to `fixed`. Legacy `full_pipeline` inputs and persisted snapshots read as `fixed`.
The `/api/v1/simulations` projection calls `in_progress` **running**.

Research receives the directive plus optional uploaded reference context.
Data receives that directive, exact `research_findings`, and uploaded context.
Analysis receives the directive and `structured_data`; Summarizer receives the
directive and `insights`; Report receives the directive and `summary`.
The exact Report text becomes `task.output`. Context is local to each run.
In `single` mode the Direct Agent receives the original directive and the same
bounded prepared uploads and safe benchmark aggregates, makes one Groq request,
and stores its answer as `task.output`. It records one stage and no handoffs.

Per-stage metrics are captured from the real LLMResponse via a ContextVar, avoiding
cross-run contamination from shared counters. Errors are credential-redacted before
being persisted. On failure, completed stages stay completed, the current stage
fails, downstream stages remain waiting, and no final success is invented.

## Endpoints

All paths below are relative to `/api/v1`.

| Endpoint | Behavior |
|---|---|
| GET/POST /tasks; GET /tasks/{id} | Compatible task creation/read API |
| GET/POST /simulations; GET /simulations/{id} | Complete run records; POST defaults to `fixed` |
| GET /simulations/metrics | Persisted aggregate, per-agent and duration history metrics |
| GET /simulations/{id}/events | Chronological real event list |
| GET /simulations/{id}/export?format=txt,json,csv | One format per request; terminal runs only |
| POST /uploads?filename=reference.txt | Raw UTF-8 file body; bounded parser |
| GET /uploads/{id} | Metadata and prepared preview |
| GET /agents; /agents/stats; /agents/{id}/stats | Roster and persisted execution statistics |
| POST /agents | Metadata only; does not create executable code |
| GET /messages; /simulation/activity | Optional simulation_id filter |
| GET /simulation/stats | Legacy aggregate view |
| POST /simulation/pause,resume,stop | Explicit supported=false; no fake state changes |
| GET /datasets; GET /datasets/{id} | Registered benchmark metadata; no raw rows |

Uploads support TXT, rectangular CSV, JSON. Maximum 256 KiB per file, three per
run. Prepared context is limited to 6,000 characters per file and 20 CSV data rows,
with an explicit truncation marker. File names are sanitized, input is never
executed, malformed files are rejected, and CSV exports escape formula prefixes.
Use `uploadIds` in task/simulation creation to actually supply uploaded context.

## Events and storage

`/ws/live` keeps the existing `{event,data,timestamp}` envelope.
Events: simulation_created/started/completed/failed, agent_started/completed/failed,
message_created, task_created/updated, message_sent, activity_event, stats_updated.
State is committed before broadcast. REST is authoritative after reconnect.

The SQLAlchemy repository uses SQLite locally and PostgreSQL via `DATABASE_URL`.
Version 2 normalizes tasks, stages, handoffs, events, metrics, uploads, dataset
metadata and roster while retaining a compatible run snapshot. On startup,
fresh schemas are created automatically. A V1 SQLite file is validated and
copied to a timestamped `.v1.*.db` backup; legacy tables are retained as
`*_v1_archive` after migration. Never delete either without a verified backup.

Provision the six authorized benchmark JSON files under `../data/benchmark/`,
then run `python -m app.datasets.cli register` from this directory. The command
validates all six before registry writes and stores metadata only. Clients can
list `GET /api/v1/datasets` and pass `datasetId` plus optional `taskType` in
`POST /api/v1/tasks` or `/simulations`. Each selected agent receives bounded,
non-personal aggregates; full rows, names, IDs, protected attributes, and salary
never enter benchmark context. Registration is explicit; no Drive fetch occurs.

Default database: `./simulator.db`. Start one worker only. In-progress/queued runs
become failed on restart; finished history survives on the same disk. Use backups
and a durable database for long-lived data. The Railway PostgreSQL service is
connected in production: a completed run from commit `ef27951` remained available
after a backend restart on 2026-09-29. This verifies backend-restart durability,
not survival of PostgreSQL service loss. Benchmark JSON provisioning in production
remains unverified. No automatic retention, job queue, login or ownership
enforcement exists yet. See
`../docs/PHASE2_DATABASE_DEPLOYMENT.md` for setup and migration limits.
