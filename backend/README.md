# FMProject FastAPI backend

The active default is the sequential coordinator in `app/api/routes/tasks.py`.
The installed LangGraph adapter supports Single, Fixed and Adaptive with durable,
authorized checkpoints, but `LANGGRAPH_RUNTIME_ENABLED` remains false by default.
Both paths reuse Task, StageExecution, RoutePlan, telemetry and provenance. Custom
agents and HR assistance use their bounded existing execution paths.

## Intent and output contracts

System agents use prompts-v2-intent / contracts-v2-output. ExecutionContext keeps
an immutable original directive; each prompt carries that request, a stage objective,
original reference sources, an explicitly unverified bounded predecessor excerpt,
and request-derived output requirements. The prior output never becomes the request.
Research/summary prompts no longer impose a universal 200-word response cap.

Final-stage format checks are saved as optional StageExecution.outputContract in
existing Task JSON evidence. Raw provider outputs remain exact. Common explicit
JSON keys, bullet counts and number-only requests are checked; wrappers and invalid
formats are disclosed rather than silently accepted. This is format validation,
not proof of semantic correctness or an arbitrary user-supplied JSON Schema engine.
No new table or schema migration is needed. Historical provenance is not relabeled;
research configuration hashes include the changed implementation.

Recycle Bin listing now reports permanentDeletionEligible and protectionReason
using the same evidence-retention check as purge. Listing eligibility is advisory;
purge still reauthorizes and rechecks atomically. Unknown eligibility fails closed
in the UI. No protected evidence can be permanently deleted.

## Local operation

Use Python 3.13 (validated with 3.13.3); the current dependency minimum is 3.10.
From the repository root, create/activate `.venv` and install the current manifest:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend
cp .env.example .env
python run.py
```

Copy the template only for a fresh setup; never overwrite an existing private `.env`.
The [root setup guide](../README.md#local-development) explains Google development
client registration, frontend setup and connection diagnostics. Backend settings
come from `app/core/config.py`, process environment and working-directory `.env`.
The template's local SQLite URL selects `backend/simulator.db`; startup creates and
initializes a fresh database, and may migrate an existing one. Back up existing local
data before a version upgrade. No production database or manual fresh-SQLite migration
is needed. Use one worker and keep graph/checkpoint/live-research defaults disabled.

Google sign-in requires `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
`GOOGLE_REDIRECT_URI` and `FRONTEND_URL`. Register
`http://localhost:8000/api/v1/auth/google/callback` on an authorized Google OAuth
web development client. Keep its secret private; cloning GitHub does not supply it.
Anonymous `/api/v1/auth/me` returns 401; blank OAuth configuration returns 503 at
login. The login page can render without configured OAuth, but workspaces require
real sign-in. Groq credentials are needed only for actual AI requests; Ollama is
inactive. Never print keys or put them in frontend settings.

Tests use disposable stores and mocked provider calls. From the repository root,
`.venv/bin/python -m pytest backend/tests` runs the suite; restricted local PostgreSQL
checks require separately approved test credentials and otherwise skip. Do not point
tests at production storage. `python -m pip check` checks the installed environment;
a successful check does not prove a fresh installation.

## Contracts and APIs

Python uses snake_case; CamelModel emits camelCase. `/api/v1/tasks` retains
queued/in_progress/completed/failed; the simulation projection names in_progress
running. `/simulations` defaults to Fixed; legacy `/tasks` without a mode selects
an individual specialist. Legacy full_pipeline maps to Fixed. Single is the
neutral Direct baseline; Adaptive uses deterministic rules-v1 and no routing LLM.

| API namespace | Implemented responsibility |
| --- | --- |
| `/auth` | Google login/callback, session check and logout/revocation. |
| `/workspaces` | Private workspace discovery, organization create/join, IAM member/HR-role management. |
| `/tasks`, `/simulations` | Admit/read runs, events/metrics/terminal TXT/JSON/CSV export, explicit gated graph resume and evaluation. |
| `/uploads` | Owned, bounded TXT/CSV/JSON prepared reference context. |
| `/agents`, `/messages`, `/simulation`, `/datasets` | System roster and saved telemetry/evidence/registered benchmark metadata. Legacy pause/resume/stop report unsupported. |
| `/agent-builder` | Owned revisioned text-agent definitions, options, immutable history and runs. |
| `/recycle-bin` | Manager restore/list and owner-only eligible purge. |
| `/hiring` | Requirements, knowledge, JDs, immutable revisions, exact source usage and human review/approval. |
| `/hiring/agents` | Revision-bound requirement assessment, JD proposals and validation; saved private evidence. |
| `/experiments` | Matched modes and Research Lab benchmarks/admission/history/comparison/rerun/report/human rubric. |
| `/ws/live` | Origin-validated authenticated workspace event hints; REST recovery after reconnect. |

Uploads are at most three × 256 KiB; prepared context is bounded to 6,000 characters
per file and 20 CSV rows. CSV exports escape formula prefixes. Files are not executed,
PDF is unavailable, and raw upload bytes are not an archival storage facility.

Schema **13** contains 22 tenant-owned tables with PostgreSQL ENABLE/FORCE RLS.
Trusted transactions bind user/workspace identity and clear it on commit/rollback.
Personal Workspaces have no organization HR authority. Workspace IAM and HR human
roles are separate. Generic simulation APIs exclude HR evidence. HR source access
is checked before reading, before provider execution and before accepting output.
Human approval remains pinned to the exact submitted revision.

Use one worker: execution is in process and startup recovery is not coordinated
across multiple live servers. Restart marks interrupted runs failed. Explicit graph
resume requires a separate restricted checkpoint login/schema; no runtime migrations,
BYPASSRLS or table-owner membership. Evidence/checkpoint reconciliation avoids repeating
committed stages but cannot guarantee exactly-once external provider requests.

Research admission and the model judge are disabled by default. Fixture machinery
acceptance does not establish live quality, latency, usage/cost advantage or significance.
The reproduction script accepts `--output` to preserve historical reports.

See [current architecture](../docs/FINAL_PROJECT_GUIDE.md),
[release/security gates](../docs/RELEASE_READINESS.md),
[final acceptance](../docs/PHASE10_ACCEPTANCE_REPORT.md),
[checkpoint contracts](../docs/PHASE4_LANGGRAPH_RUNTIME.md), and
[research methodology](../docs/PHASE9_RESEARCH_EVALUATION.md).
