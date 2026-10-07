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

Run from this directory with a virtual environment containing `requirements.txt`:

```sh
python run.py
python -m compileall -q app tests scripts
```

Run regression from the repository root with `.venv/bin/python -m pytest backend/tests`.
No dependency reinstall is necessary in the accepted checkout. Settings come only
from `app/core/config.py`, environment variables and working-directory `.env`.
The relative SQLite path selects `backend/simulator.db` when run here; choose
`DATABASE_URL` explicitly if another local database is intended. Never print keys.
Copy `.env.example` to `.env` for documented placeholders. Tests use disposable stores and mocked providers.
Google authentication and Groq execution require separately supplied configuration.

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
