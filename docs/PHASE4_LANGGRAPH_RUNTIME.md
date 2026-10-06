# Phase 4.7 — LangGraph runtime integration

## Status and reconciliation

The Single, Fixed, and Adaptive graphs (4.7.1–4.7.5) already existed at
`d4ea9fb`. Phase 4.7 now includes an executable graph runtime adapter, authorized
checkpoint lifecycle, recovery endpoint, and deterministic evidence/telemetry
coverage. **Acceptance remains incomplete and the sequential runtime stays
active by default.** A dedicated restricted checkpoint runtime login and real
Psycopg persistence/reconnect acceptance are outstanding. No Phase 4.8 work,
production changes, deployment, or push is included.

Historical Phase 4.5 notes are snapshots, not current completion claims:
`d2a31c0` committed HR human-role RLS; `f2548f1` committed upload ownership and
tenant-scoped isolation; `01c6edb` added live PostgreSQL verification;
`3ae6df0` committed organization member removal. The earlier uncommitted
4.5.5B changes therefore no longer need reimplementation. Current live tests
still require explicit local test credentials; historical test counts are not
substitutes for this run's results.

## Authoritative boundaries

ExecutionContext remains immutable validated input and successful handoffs.
Task and StageExecution remain the only task/stage lifecycle and evidence
records. RoutePlan chooses and records Adaptive routes; the graph never
reroutes. GraphRunState contains orchestration identity, context, and graph
cursor only. `graph_runtime.execute_graph` binds graph nodes to the existing
`tasks._run_stage`, `record_message`, `emit`, evaluation, provenance, activity,
and task persistence functions. The legacy `agents/orchestrator.py` is not an
execution authority.

Single runs direct; Fixed runs the existing five specialists; Adaptive runs
only the validated persisted route. Individual-specialist `single_agent`
requests retain their original runtime. Selected stages must exactly match the
route, and completed evidence must form a nonempty-output prefix. No evidence
is fabricated for skipped agents. Existing creation, read, evaluation, progress,
stage, message, statistics, and terminal event payloads remain compatible.

## Checkpoint authorization and connection lifecycle

`checkpoint_thread_id` hashes a JSON tuple of workspace and task with SHA-256,
using a version prefix. Missing workspace/task identity fails closed; separator
collisions cannot alias two pairs. Thread IDs are constructed internally and
are never accepted from API callers. Stored legacy checkpoint identifiers and
msgpack rows are preserved, but are not automatically imported into this runtime.

Before opening a checkpoint connection, the trusted worker verifies IAM
`simulation.create`, active workspace access, and tenant-scoped task visibility.
Organization members may resume tasks visible through the existing IAM rules;
legacy `owner_id` is not a new ownership restriction. HR human roles grant no
checkpoint permissions. Every saver operation rechecks authorization, including
membership revocation. Namespace overrides, global listing, foreign thread
configuration, and foreign thread deletion are rejected.

The saver opens one Psycopg connection per task operation and closes it on
success, error, or cancellation. It performs **no migrations**. Runtime
validation rejects superuser/BYPASSRLS, schema CREATE, table-owner membership,
reachable bypass-role membership, application-table privileges, migration-table
access, missing ENABLE/FORCE RLS, and unexpected policy expressions. It pins an explicit
dedicated search path. Each cursor executes inside a transaction, installs
`app.checkpoint_thread_id` with `set_config(..., true)` on that connection, and
commits or rolls back before returning. Pipeline mode is intentionally disabled
in this subclass so context and query share one bounded transaction.

All three checkpoint data tables have the reviewed equality USING/WITH CHECK
policy. `checkpoint_migrations` stays migration-only. SQLAlchemy tenant context
is never assumed to propagate into Psycopg. A connection-scoped PostgreSQL
advisory lock prevents concurrent graph workers for the same versioned task
identity; close/crash releases the lock. The application reloads task evidence
after acquiring it and checks start/resume eligibility again.

**Threat boundary:** authenticated identity comes from the trusted API/worker,
not graph input or client-provided IDs. RLS protects saver queries against
missing/mismatched connection context. As with the existing application tenant
GUC model, a compromised database login or arbitrary SQL executing as the
trusted service could set another thread's GUC. This is not cryptographic
authorization against credential compromise. Do not expose a raw saver, DSN,
or SQL interface to users. No claim of such protection is made.

The serializer uses data-only JSON with one explicitly validated
ExecutionContext tag, restoring nested AgentOutput and frozen models. It does
not use pickle or dynamic imports. These graphs do not support arbitrary custom
Send/message objects. Serializer/graph-version changes require a migration and
recovery regression gate.

## Local database state and provisioning gate

Local inspection confirmed `fm-tenant-postgres`, PostgreSQL 16,
`fm_tenant_test`, port 55432. The dedicated `langgraph_checkpoints` schema and
four migration-owner tables already existed. This work applied
`backend/migrations/checkpoint_security.sql` only to that local schema,
enabling FORCE RLS on the three data tables and installing task policies.
Existing dedicated/public checkpoint records were not deleted. `fm_app` retains
neither USAGE nor CREATE in the dedicated schema.

`fm_checkpoint` is the existing NOLOGIN, NOSUPERUSER, NOBYPASSRLS,
NOCREATEDB, NOCREATEROLE, NOINHERIT migration/table-owner role. No authorized
runtime login or role membership existed. No login/password was created or
reset. Host access as existing `fm_app` without a password did not work.

An operator must privately provision a **separate** NOSUPERUSER/NOBYPASSRLS
runtime login, with USAGE on the checkpoint schema and only
SELECT/INSERT/UPDATE/DELETE on `checkpoints`, `checkpoint_blobs`, and
`checkpoint_writes`. Grant no schema CREATE, migration-table privileges,
owner-role membership, or application schema access. Use migration credentials
only for `AsyncPostgresSaver.setup()` and the reviewed RLS migration, separately
from the service. Never use PostgreSQL superuser credentials in the application.
For future migrations, inspect existing policies before applying the security
SQL: policy creation intentionally refuses an existing duplicate rather than
silently replacing an unknown policy.

Settings live only in `app/core/config.py`:

- `LANGGRAPH_RUNTIME_ENABLED=false` (safe default; retain until acceptance passes)
- `CHECKPOINT_DATABASE_URL` (private runtime URL; never reuse the application URL)
- `CHECKPOINT_SCHEMA=langgraph_checkpoints`

There is no Railway configuration change. Activation requires all three modes
passing real saver persistence/reconnect tests, application PostgreSQL tenant
regressions, concurrent-worker checks, and production-specific configuration,
role grants, WebSocket, and restart validation. Until startup recovery is validated across multiple live server processes,
deploy with a single server worker: startup recovery predates the graph lock
and can mark another process's task interrupted. Do not enable merely because
the graph unit tests or schema checks pass.

## Failure, retry, restart, and checkpoint/evidence reconciliation

Graph invocation uses synchronous checkpoint durability: a write must complete
before the next stage. Agent failure creates a failed stage and failed task;
no final output is published. Startup continues the existing tenant-scoped
recovery transaction, marking active stages and interrupted tasks failed.
It does not auto-resume or replay a provider call.

`POST /api/v1/tasks/{task_id}/resume` is an authenticated, workspace-scoped,
202 endpoint using `simulation.create`. It is disabled while the graph runtime
is off. Only failed graph-mode tasks without an input-contract failure and with
a valid durable checkpoint are eligible. It checks the checkpoint before
scheduling work; a missing/drifting checkpoint returns 409, unavailable
checkpoint infrastructure returns 503. The response is the current persisted
Task; background execution then emits the existing start and terminal events.
No thread ID, arbitrary state, or historical checkpoint ID can be supplied.

Resume loads the checkpoint and compares its input context, route prefix,
workspace/task identity, and outputs with authoritative evidence. Evidence may
be ahead of a checkpoint if a stage committed just before a crash: replay uses
the committed output without repeating the agent, repairs a missing handoff,
and avoids duplicating the matching handoff/event. Checkpoint success ahead of
stage evidence or changed inputs/outputs fails closed. Completed terminal graph
state can finalize a task whose final task commit was interrupted. Incomplete
stages retry using their existing records; no second StageExecution is created.

Known provider usage and measured duration accumulate across retries rather
than discarding failed-attempt measurements. Unknown/unreturned provider usage
cannot be inferred. The stage's model and attempt timestamps describe the most
recent attempt; Task elapsed time accumulates worker attempts. Interrupted attempt duration
is estimated from the last start to startup recovery and may include downtime. Existing events retain failed/completed attempt history.
Quality evaluation remains explicit and is not automatically invoked.

**Limitations:** external provider calls and database evidence writes cannot
share an atomic commit with graph checkpoints. If a process dies after a
provider responds but before successful StageExecution evidence commits, a
retry can repeat that call. Exactly-once external side effects are not promised.
This follows LangGraph's documented need for idempotent side effects:
[LangGraph durable execution](https://docs.langchain.com/oss/python/langgraph/durable-execution).
Checkpoint failure stops execution; application database failure may prevent
terminal failure persistence until startup recovery can access it again.
WebSockets are best-effort notifications after evidence persistence, not an
exactly-once delivery queue; reconnect clients read persisted tasks/events.

## Validation commands and safety

Run from the repository root using the existing `.venv`; no dependency
reinstallation, providers, multiple servers, or parallel workers are required:

```sh
.venv/bin/python -m pytest -q backend/tests/test_checkpointing.py backend/tests/test_graph_runtime.py
.venv/bin/python -m pytest -q backend/tests/test_postgres_checkpoint_runtime.py
RUN_LOCAL_CHECKPOINT_SQL_TESTS=1 .venv/bin/python -m pytest -q backend/tests/test_checkpoint_postgres_sql.py
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q backend/app
.venv/bin/python -m pip check
git diff --check
```

Privately configure `CHECKPOINT_TEST_DATABASE_URL` for the restricted checkpoint
login and `TENANT_TEST_DATABASE_URL` for the established application test login.
The real saver tests require localhost and exactly `fm_tenant_test`; they never
fall back to application/production settings, run setup(), create/drop existing
tables, or perform broad cleanup. Cleanup deletes only a fresh authorized test
thread. Application RLS fixtures create and drop only random test-owned schemas.
Review them before use. The opt-in Docker SQL test creates random temporary
copies, runs assertions as non-bypass `fm_app` with `fm_checkpoint` owning the
tables, and rolls back the entire test; it does not create credentials or touch
existing records. Its success is SQL RLS proof, **not** saver reconnect proof.

Skipped PostgreSQL acceptance cases remain unverified gates. The final chat
report contains this run's actual counts and commits; historical phase documents
retain their original evidence rather than being silently rewritten.

## Validation recorded on 2026-10-06

Final command:
`RUN_LOCAL_CHECKPOINT_SQL_TESTS=1 .venv/bin/python -m pytest -q --tb=short`
completed with **445 passed, 30 skipped, 2 warnings** in 19.16 seconds.
The 30 skips are 27 existing application PostgreSQL cases requiring
`TENANT_TEST_DATABASE_URL` and three new saver acceptance cases requiring
`CHECKPOINT_TEST_DATABASE_URL`. The rollback-only local Docker RLS test was
included and passed. No provider calls were used.

The focused graph runtime suite passed all 19 cases, including enabled worker
dispatch, authenticated resume API and cross-workspace denial, all-mode failure
and recovery, metrics preservation, restart handling, checkpoint failure before
execution and after evidence commit, duplicate-stage prevention, and denial of
fabricated terminal checkpoint output. Compilation and `git diff --check`
passed; `pip check` reported no broken requirements (with a harmless cache
permission warning). The two suite warnings concern LangChain serialization
and Starlette/AnyIO deprecations. Runtime remains disabled and the sequential
implementation remains authoritative until the skipped acceptance gates pass.
