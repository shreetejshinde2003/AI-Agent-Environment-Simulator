# Phase 4.5.5A — Workspace and membership bootstrap RLS

Historical checkpoint record: local 4.5.5B now activates HR assignment RLS and
scopes its operations. See [current HR-role behavior](PHASE4_HR_HUMAN_ROLE_RLS.md)
for the expanded activation set and current workflow. Upload ownership/RLS and
live PostgreSQL verification remain incomplete; the 4.5.5A results below are not
a claim of subsequent production verification.

## Status

COMPLETED (local implementation): authenticated-user bootstrap, scoped
organization creation/join/member management, two-table RLS activation and
bounded startup catalog recovery. Google authentication/session behavior, IAM
permissions, SQLite development and simulation execution remain unchanged.
No table/column, schema-version, dependency, frontend or deployment change.

PARTIAL (verification): deterministic and SQLite/API validation completed.
Real PostgreSQL enforcement/pool tests remain opt-in and skipped without
`TENANT_TEST_DATABASE_URL`. This checkpoint has not been deployed or production
verified. Phase 4.5 as a whole remains PARTIAL.

## Trust chain and transaction-local contexts

Authenticated session → active stored user → authenticated `user_id` →
`bootstrap_transaction()` → authorized workspace discovery → selected workspace
and authenticated user in `tenant_transaction()`.

The frozen typed `BootstrapSessionContext` contains only `user_id`. Bootstrap
sets `app.current_user_id` and explicitly clears `app.current_workspace_id`;
it does not pretend a workspace is selected. Invalid identity fails before
checkout. All context settings use parameterized `set_config(..., true)`, never
session defaults. Every context transition resets unrelated capabilities. Commit
and rollback restore local settings; subsequent pooled borrowers must not inherit
them. SQLite validates identity but executes no PostgreSQL context SQL.

Three additional settings implement bounded internal operations, not ordinary
bootstrap request parameters:

| Setting | Trusted source and purpose |
| --- | --- |
| `app.invitation_digest` | SHA-256 digest of an authenticated join request's secret code; active organization lookup matches only that digest, in addition to ordinary own-workspace visibility. No plaintext code is set. |
| `app.invitation_workspace_id` | ID from the database row matched by that digest, never an arbitrary request workspace; permits only the user's own membership read/reactivation/insert. |
| `app.recovery_owner_user_id` | Persisted identity catalog ID used only alongside `system:startup-recovery` for creator/owner-bounded catalog discovery, including inactive workspaces. |

Normal bootstrap and selected-tenant contexts clear all three capabilities.
Invitation and recovery clear the selected workspace and each other's capability.
No route accepts these settings directly from client headers or payloads.

## RLS activation and visibility

Newly activated: **`workspaces`, `organization_memberships`**, both with
`ENABLE ROW LEVEL SECURITY` and **`FORCE ROW LEVEL SECURITY`**.

The original eight data-plane tables remain active: `simulations`, `tasks`,
`agent_executions`, `agent_messages`, `activity_events`, `run_events`,
`simulation_metrics`, `simulation_uploads`. `ACTIVE_RLS_TABLES` is the explicit
union of the eight-table data-plane set and the two-table bootstrap readiness set.
Newly classified tables do not activate automatically.

- Missing user context sees no workspace/member rows, even if only a workspace
  setting exists.
- Ordinary bootstrap sees only the user's own active Personal Workspace and
  active organizations with their own active membership. Creator identity alone
  grants no ordinary organization discovery rights.
- Membership discovery shows only active own memberships. Inactive membership
  cannot expose its organization. Workspace/API checks also exclude inactive
  organizations; the membership table records membership state independently.
- Selected-workspace transactions expose only that workspace and its members,
  not every other organization the same user belongs to.
- The workspace policy reads memberships; the membership policy never queries
  workspaces, deliberately avoiding recursive policy expansion.

Explicit SQL predicates and application IAM authorization remain defense in
depth. RLS is tenant isolation, not a replacement for Owner/Admin/Member checks.

## Creation, invitation and IAM writes

Personal Workspace provisioning inserts an active workspace owned/created by the
authenticated user. Existing uniqueness/concurrency reread preserves idempotent
Google login provisioning.

Organization creation inserts an authenticated creator-owned organization under
bootstrap, then switches to the freshly generated/inserted workspace ID for its
first Owner membership in the **same transaction**. Either both inserts commit or
both roll back. No unrestricted catalog connection is opened.

Joining is a secret-code capability, separate from ordinary discovery. The digest
resolves an active organization; only then is its matched ID installed as an own-
membership invitation scope, with normal selected-workspace context still unset.
Invalid/inactive codes share the same error. Rejoining preserves Owner/Admin/Member
roles and can reactivate an inactive own membership. Other users' membership
records are not accessible through this capability. IAM role values still come
from existing trusted join/management logic, not a role supplied to the join API.

User-only discovery has no membership write grant. Target-member reads carry
actor identity separately from target identity. Role changes resolve the actor
through bootstrap, then recheck active memberships, permissions and last-owner
protection inside the selected-workspace transaction. HR role assignments only
have their prerequisite workspace/member reads adapted; HR-table RLS is deferred.

Unscoped workspace get/save, membership save and member listing reject PostgreSQL
usage before checkout. Their historical SQLite fixture compatibility remains.

## Startup recovery after catalog protection

The former unrestricted workspace SELECT would stop finding rows under FORCE
RLS. Recovery now reads identity IDs (including inactive users), opens one bounded
creator/Personal Workspace owner catalog scope at a time with the explicit system
principal, collects/deduplicates workspace IDs, then uses the existing locked
per-workspace recovery transactions. SQL also carries the creator/owner predicate.

`created_by_user_id` is nonnullable with a restrictive identity foreign key, so
surviving organizations retain a catalog creator even after membership loss or
identity deactivation. Thus inactive/orphan organizations remain recoverable.
The maintenance branch permits bounded catalog reads, not writes, unrestricted
run reads, a global allow-all policy, human impersonation or a bypass DB role.

Interrupted queued/in-progress runs still become failed, preserving completed
stage evidence and waiting downstream stages. No continuation, fabricated
handoff, retry or provider call. Recovery remains idempotent. Existing single-
coordinator/worker-liveness limitations in 4.5.4C remain unchanged.

## Reviewed call-site classification

| Boundary | Call sites and treatment |
| --- | --- |
| Identity-only | `auth._authenticated_record`, Google user/session provisioning, logout, repository users/sessions: existing identity transactions; authentication precedes bootstrap. |
| Bootstrap before selection | `auth.me`, personal provisioning; `workspaces.list_workspaces`, personal lookup/ensure, `resolve_workspace_for_user`, IAM resolution, prerequisite HR workspace reads, `main` WebSocket workspace resolution: user-bound transactions and explicit filters. |
| Bootstrap writes/invitation | Authenticated organization create/join endpoints and repository workflows: atomic generated-workspace creation and secret-scoped invitation context. |
| Selected tenant | Member listing/target inspection/role changes, existing tasks/simulations/messages/experiments and background execution: authenticated actor plus authorized workspace. Simulation execution/routing unchanged. |
| Startup/maintenance | `main.lifespan`, initialize/recovery: existing role/advisory-lock preflight; identity catalog then owner-bounded workspace discovery then per-tenant locked recovery. |
| System-global | Schema version, dataset registry and agent roster: existing ordinary metadata transactions. |
| Deferred HR roles | Assignment/list/deactivation direct transactions retain IAM/HR checks and workspace predicates; HR-table wiring/activation waits for 4.5.5B. |
| Deferred uploads | Upload save/get and task upload projection remain unowned; this checkpoint makes no upload isolation claim. |
| Legacy/internal compatibility | Unscoped workspace/member and simulation helpers plus SQLite migrations/backfill: SQLite-only. `_save_task` uses its caller's scoped connection on PostgreSQL. |

Remaining `engine.begin/connect` calls were reviewed by containing method, not
mechanically replaced. Self-membership lookup carries its authenticated `user_id`;
target inspection supplies a separate trusted `actor_user_id`.

## Deployment and verification limits

Policy refresh is code-versioned/atomic under the existing initialization advisory
lock; schema version remains 8. Unsafe superuser/BYPASSRLS roles or memberships,
unknown policies on any ready table, deferred HR-role activation and unowned
first-activation simulation history still block startup. No role grants,
credentials or application data are silently changed. FORCE remains mandatory.

An older release that rejects bootstrap activation fails closed if rolled back
after these policies are installed. Roll forward with reviewed compatible code;
do not disable FORCE as a rollback shortcut. No deployment/settings were changed.

As before, initialization needs schema/policy-owner privileges. This protects
against missing filters, not arbitrary SQL by a compromised application capable
of setting trusted settings. Separate runtime/migration-role hardening is a later
operational concern, not a bypass ordinary traffic path. See primary
[PostgreSQL RLS documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
and [policy semantics](https://www.postgresql.org/docs/current/sql-createpolicy.html).

Deterministic tests cover typed validation, parameterized local settings, context
transitions, actual policy predicates evaluated with SQLite fixture records,
private/nonmember/inactive visibility, selected-workspace narrowing, no bootstrap
write grant, actor/target separation, IAM compatibility and recovery scope.
SQLite predicate evaluation is **not PostgreSQL enforcement verification**.

The opt-in PostgreSQL tests cover unfiltered discovery, foreign-owner writes,
missing context, inactive membership/rejoin, the same pooled backend after commit
and rollback, selected-tenant transition, invitation isolation, IAM/last-owner
checks, bootstrap write denial and inactive/orphan recovery. The disposable local
schema fixture uses a one-connection pool and rejects superuser/BYPASSRLS logins.
It never uses production `DATABASE_URL`. Set `TENANT_TEST_DATABASE_URL` explicitly
to a local isolated test DB to run them; no service is implicitly installed.

## Remaining Phase 4.5 gates

Local validation on 2026-10-04:

- Focused bootstrap/RLS/recovery/authentication/IAM/API suite: **120 passed,
  16 skipped**, one existing warning.
- Full `pytest`: **350 passed, 16 skipped**, one existing warning.
- `python -m compileall -q backend`: passed.
- `git diff --check`: passed.
- Skips: six existing data-plane and ten new bootstrap PostgreSQL enforcement
  cases; `TENANT_TEST_DATABASE_URL` is not configured.
- Warning: Starlette TestClient's deprecated AnyIO `BlockingPortal` alias.
- Provider/Groq calls: **0**. No staging, commit, push or deployment.

NOT IMPLEMENTED here:

- 4.5.5B: HR human-role transaction wiring and RLS activation.
- 4.5.5C: upload ownership schema, tenant-scoped upload API and upload RLS.
- 4.5.6: final adversarial and live PostgreSQL/production verification.
- Phase 4.6 or any frontend/execution/routing/provider feature.

No staging, commit, push or commit-message recommendation until all Phase 4.5 is
complete. Stop after this intermediate checkpoint.
