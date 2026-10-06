# Phase 4.5.4C — Data-plane RLS activation and startup recovery

**Historical implementation checkpoint.** Its schema counts, partial test results
and remaining-gate lists describe that commit. Current schema 11 protects all
14 tenant-owned tables, including uploads and custom agents/revisions. See
[Phase 4 final acceptance](PHASE4_FINAL_ACCEPTANCE_REPORT.md) for current
independently rerun evidence and outstanding production gates.

Historical checkpoint record: local 4.5.5A additionally activates workspace and
membership bootstrap RLS and replaces the deferred global catalog read with
bounded creator/owner discovery. The sections below describe 4.5.4C, not the
expanded current set. See [the bootstrap checkpoint](PHASE4_WORKSPACE_BOOTSTRAP_RLS.md)
for current behavior and verification limits. No new production verification is claimed.

## Status and scope

COMPLETED (implementation): PostgreSQL initialization now installs the explicitly
ready simulation data-plane subset. SQLite remains unchanged as the local fallback.
Authenticated request/background operations continue carrying the resolved
workspace and authenticated user. API RBAC and explicit SQL workspace predicates
remain mandatory defense in depth. No coordinator, agent, routing, provider,
frontend, deployment setting, table/column, or schema-version change was made.

PARTIAL (verification): deterministic activation/control-flow, SQLite recovery,
API isolation and existing execution regression tests are available locally.
Real PostgreSQL enforcement/pool tests are opt-in; skipped tests are **not** proof
of PostgreSQL enforcement. This checkpoint has not been production verified.

## Actually activated subset

`install_data_plane_rls_policies()` uses a readiness allowlist, not every table
classified as tenant-owned. Each receives the existing `fm_tenant_isolation`
policy, `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`:

- `simulations`
- `tasks`
- `agent_executions`
- `agent_messages`
- `activity_events`
- `run_events`
- `simulation_metrics`
- `simulation_uploads`

The parent policy compares `simulations.workspace_id` to transaction-local
`app.current_workspace_id`. Child policies require a visible matching simulation
and its workspace. Unset settings match no tenant. No fallback workspace, extra
permissive recovery policy, SECURITY DEFINER function, or bypass role is added.

Intentionally **not activated**:

| Table/group | Reason |
| --- | --- |
| `workspaces`, `organization_memberships` | Workspace discovery and organization join/bootstrap need a separate safely user-bound transaction design. Startup also needs a trusted workspace catalog. |
| `organization_human_role_assignments` | Existing HR-role operations have API RBAC but not transaction-local tenant wiring; needs its own readiness review. HR human responsibilities remain separate from IAM and agent roles. |
| `uploads` | Still `REQUIRES_SCHEMA_HARDENING`: no workspace/user ownership before attachment. Protecting `simulation_uploads` does not solve upload access or cross-tenant attachment. |
| `users`, `auth_sessions` | Identity/session boundary, not workspace RLS. |
| `schema_version`, `dataset_registry`, `agent_roster` | System-global metadata. |

The old full-set installer remains a definition/testing utility, **not** the
startup path. It must not be used to activate bootstrap tables prematurely.

## Initialization and deployment preconditions

PostgreSQL initialization holds the existing transaction advisory lock, checks
the runtime role before schema initialization, applies existing migrations, then
preflights/installs only the data-plane policies in the same transaction. Failure
rolls back the transaction and prevents API startup. Restarting re-applies the
reviewed policies and ENABLE/FORCE; no destructive data migration is introduced.

The connected login and effective role must be `NOSUPERUSER NOBYPASSRLS`, with no
membership in superuser/BYPASSRLS roles. Checking the login as well as current role
prevents connecting as a bypass-capable login and temporarily using SET ROLE to
pass preflight. PostgreSQL superusers/BYPASSRLS roles ignore FORCE RLS; merely
installing policies on those credentials would be false hardening.
See [PostgreSQL row-security documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).

The application role needs the existing initialization/migration privileges and
ownership (or suitable ownership membership) for policy DDL on these tables.
An operator must arrange this **before deploying**; this code does not create
roles, change DATABASE_URL, grant itself privileges, or modify Railway settings.
Do not leave normal application traffic on a superuser URL, grant BYPASSRLS, turn
off FORCE, or add an allow-all policy to get startup working. If the current
Railway credentials are bypass-capable, startup deliberately refuses them.

This is defense against missing workspace filters, not against arbitrary SQL
execution by a compromised application. The current startup-initialization design
needs table-owner DDL authority; a separate least-privilege runtime/migration-role
deployment is a later operational hardening concern. No privileged ordinary
traffic path or alternate global data connection is added here.

Preflight also refuses:

- Extra/unreviewed policies on a data-plane table (permissive policies can OR
  together and weaken tenant filtering). Operator policies are not silently deleted.
- Already-enabled RLS on deferred bootstrap/HR-role tables. This checkpoint does
  not disable them or pretend its current bootstrap calls can safely use them.
- Workspace-less legacy simulations before first activation. They are retained,
  not claimed by whichever person next logs in and not silently hidden by RLS.

### Legacy PostgreSQL ownership

Back up the database and inspect NULL-workspace rows using an operator connection
before enabling data-plane RLS. Review and assign each legacy run to an existing,
authorized workspace explicitly, within a controlled transaction. Use reviewed
run IDs and workspace IDs; do not infer ownership from names, arbitrary email, or
the first new account. Check affected counts before committing. No application
API exposes this maintenance operation. Existing scoped runs must not be reassigned.

`backfill_legacy_simulations_for_user()` remains operational for SQLite legacy
history only. It returns zero without accessing simulations on PostgreSQL. The
PostgreSQL startup ownership preflight is performed before initial activation;
if policies were previously enabled externally, an operator must separately audit
any already-hidden unassigned history. RLS cannot reveal such rows to the normal
application role, and this code never disables RLS to inspect them.

## Tenant-local pooled connections

All tenant operations retain `tenant_transaction()` and the existing parameterized
`set_config(..., true)` for both workspace and principal. Values are local to the
transaction, restored on commit/rollback, and never installed as session defaults.
No context is inferred from a previous pooled connection or raw client header.
The request permission gate resolves/authorizes the workspace first.

Legacy `save`, `get`, `list`, `get_for_workspace`, and `list_for_workspace` now
raise `TenantContextError` on PostgreSQL **before connecting**. They still work
for SQLite development/legacy tests. Losing a context must fail explicitly,
not turn into empty-looking production history/statistics or an unscoped write.

## Startup recovery

`tasks.recover_interrupted()` delegates to
`Repository.recover_interrupted_tasks(_mark_interrupted_failed)`:

1. PostgreSQL enumerates only IDs from the deliberately deferred workspace catalog,
   including inactive workspaces. It never globally queries simulation payloads.
2. Each workspace gets a separate tenant transaction and explicit trusted
   `system:startup-recovery` principal. This is an internal maintenance identifier,
   not an authenticated human, not a persisted user, not a special database role,
   and not an additional RLS grant. Ordinary policies still apply.
3. Only that workspace's queued/in-progress runs are selected with `FOR UPDATE`.
   Mutation and all relational evidence writes use the same locked transaction.
4. Interrupted runs become failed, lose any purported final output, receive a
   completion timestamp and a real `simulation_failed` record. Active stages
   become failed. Completed stages, outputs, token evidence and messages survive;
   waiting downstream stages remain waiting/not started. No fabricated handoff,
   retry, model call, or resumed execution occurs.
5. Repeating recovery creates no duplicate failures for already-terminal runs.
   A persistence failure rolls back the current workspace and propagates to
   startup; previously committed workspaces remain terminal on the next attempt.

SQLite recovery also supports old workspace-less local records. Duration through
restart remains elapsed run wall time when a start exists, **not** newly measured
provider latency. Missing model/token evidence is not synthesized.

Row locks prevent duplicate recovery of the same pending rows by concurrent
recovery transactions. They do **not** prove another coordinator is dead: the
existing execution model has no worker lease/heartbeat. Use the existing single
execution-coordinator deployment for restart recovery; independent live replicas
or rolling overlap require later liveness-aware recovery design, not an RLS bypass.

## Audited call-site classification

| Boundary | Calls/operations | Decision |
| --- | --- | --- |
| Authenticated tenant data plane | Task/simulation reads, exports, events, quality-evaluation persistence, metrics/activity/messages; matched-experiment enqueue | Keep `*_for_tenant` with resolved workspace and user; background execution retains the same principal. |
| Authenticated tenant-derived agent telemetry | `agents.list_agents`, `list_agent_stats`, `get_agent`, `get_agent_stats` previously called global `list` | Now require simulation-view RBAC and use `list_for_tenant`; optional `X-Workspace-Id`, otherwise Personal Workspace. Response shapes unchanged. |
| Unsupported legacy control response | `/simulation/pause`, `/resume`, `/stop` previously called global `aggregate()` | Still unsupported; return only authorized workspace statistics, never execute controls. |
| Internal/legacy compatibility | Fallback `save` in task emit/enqueue and activity/message recording; `get_record` fallback get/get_for_workspace; aggregate default, metrics default/list_for_workspace, register-task fallback, unused `get_message_count` | SQLite-only compatibility. PostgreSQL legacy repository guard rejects missing principal; authenticated API/background branches already pass both identities. |
| Startup/maintenance | `main.lifespan`, old recovery global list/save | Initialization then catalog enumeration and scoped recovery; no global data-plane connection. |
| Bootstrap/identity | Auth users/sessions, Personal Workspace provisioning, workspace discovery/resolution, organization creation/join, membership/IAM and HR-role operations | Existing explicit authorization remains; direct engine transactions touch only intentionally deferred/identity tables. PostgreSQL legacy simulation backfill no longer opens a transaction. |
| System-global | Dataset registry get/list/save, roster metadata get/save and static relationships | Ordinary transactions acceptable for genuinely shared metadata, not per-run telemetry. |
| Upload hardening blocker | Upload save/get and `_save_upload` used during task projection | Intentionally deferred; no claim of tenant ownership isolation. |

Direct `engine.begin/connect` occurrences in `database.py` were reviewed by
containing method, not mechanically replaced. Initialization/migrations are
startup/system operations; V1/SQLite backfill and legacy run methods are local
compatibility; identity/workspace/membership/HR-role methods remain deferred;
registry/roster methods are global. `_save_task`/`_upsert` accept the caller's
connection, which is tenant-scoped for PostgreSQL request/background/recovery.
`tenant_db_context.engine.begin()` is the shared trusted transaction boundary.

No frontend change is needed for existing simulation contracts. Agent telemetry
supports the same optional workspace header as other scoped APIs; callers omitting
it receive Personal Workspace telemetry, never organization/global telemetry.

## Validation without providers

Focused tests cover activation allowlisting and FORCE, role/ownership/policy
preflight, SQLite fallback, legacy PG guardrails, locked tenant recovery control
flow, recovery rollback/idempotency, inactive workspace recovery, and tenant-scoped
agent telemetry. Existing RBAC/background/pipeline suites remain regression gates.

Real enforcement tests in `backend/tests/test_postgres_data_plane_integration.py`
are gated by **TENANT_TEST_DATABASE_URL**, never application DATABASE_URL. Supply
an isolated localhost PostgreSQL test database and a non-bypass login able to
create schemas. Host-overriding connection parameters are refused. Each test
creates/drops only its own randomly named schema. Tests exercise actual FORCE RLS,
all eight tables, cross-tenant reads/writes, shared pooled connection reuse after
commit/rollback, repeat activation, and recovery. No providers or HTTP-created runs.

```sh
source .venv/bin/activate
# Set TENANT_TEST_DATABASE_URL privately to an isolated LOCAL test database.
pytest -q backend/tests/test_postgres_data_plane_integration.py
pytest
python -m compileall -q backend
git diff --check
```

If no test server is configured, these six PostgreSQL tests explicitly skip.
Do not label that as real PostgreSQL or production validation. Do not point tests
at Railway. No new dependency or PostgreSQL installation is required for SQLite
tests/development.

### Local results (2026-10-04)

- Focused activation/recovery/telemetry plus tenant context, execution, pipeline,
  RBAC and multi-tenant regression group: **91 passed, 6 skipped**, one warning.
- Full `pytest`: **330 passed, 6 skipped**, one warning (336 collected).
- `python -m compileall -q backend`: passed.
- `git diff --check`: passed.
- Known warning only: Starlette TestClient's AnyIO `BlockingPortal` deprecation.
- PostgreSQL tests skipped because `TENANT_TEST_DATABASE_URL` was not configured.
  No local PostgreSQL binaries were found; the installed Docker application could
  not launch (missing executable) and its daemon was unavailable. Infrastructure
  repair/installation was not attempted. No production database was contacted.
- Zero provider calls; no real simulations, frontend or deployment changes.

The skipped integration tests are the remaining acceptance gate for actual
PostgreSQL enforcement and pooled-connection cleanup, not six passing tests.

## Remaining Phase 4.5 blockers

- Live non-bypass PostgreSQL and production activation verification.
- Operator readiness: safe database role/ownership and reviewed legacy ownership.
- Safely user-bound workspace/membership bootstrap and HR-role transaction wiring
  before activating their policies.
- Upload ownership/scoping, orphan handling and attachment authorization.
- Audit/restrict the remaining shared metadata mutation surface separately; no
  claim is made that global custom-agent metadata is workspace-owned.

Phase 4.5 is **not completely hardened** until the deferred boundaries are solved.
No Phase 4.6 work is included.
