# Phase 4.5.5B — HR human-role transaction wiring and RLS

## Status and scope

COMPLETED (local implementation): selected-workspace HR-role transactions,
fresh IAM checks on the operation connection, explicit actor/target separation,
and PostgreSQL `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` for
`organization_human_role_assignments`.

PARTIAL (verification): deterministic SQLite, API, transaction-wiring and policy
predicate tests pass. Actual PostgreSQL enforcement and pooled-connection tests
remain opt-in; skips are not enforcement evidence. No production verification is
claimed for this checkpoint.

No schema columns/version, dependencies, frontend/API response shapes, deployment
configuration, Google session behavior, execution modes or routing changed.
No model/provider requests are needed. Upload ownership is NOT IMPLEMENTED here.

## Trust boundary and call-site classification

Authenticated session → authenticated actor `user_id` → existing user-bound
workspace discovery/IAM authorization → `tenant_transaction(workspace_id,
user_id=actor_user_id)` → fresh active organization/membership checks → HR query.

| Call/path | Classification and behavior |
| --- | --- |
| Workspace/membership reads in `resolve_hr_human_authorization` and HR API preflight | Authorization bootstrap; existing authenticated-user discovery, never HR roles as a substitute for IAM membership. |
| `assign_organization_human_role` | Selected-workspace tenant operation; recheck actor management permission and active target membership on the same connection as the write. |
| `deactivate_organization_human_role` | Selected-workspace tenant operation; recheck actor management permission, retain history and allow cleanup after target membership loss. |
| `list_organization_human_roles(..., actor_user_id=...)` | Selected-workspace tenant operation; own active responsibilities or IAM-manager listing/history, with explicit workspace/user filters. |
| HR assignment listing without actor | Legacy SQLite/test compatibility only. PostgreSQL rejects before connection checkout; target `user_id` is never inferred to be the actor. |
| User/session reads | Identity path; unchanged. |
| Repository initialization/policy refresh | Maintenance/startup DDL under existing role guard, transaction and advisory lock. No new global HR-record scan, recovery capability or bypass. |

Authenticated application paths now pass actor identity explicitly. The target
member filter remains a separate argument, and `assigned_by_user_id` records the
actor rather than the target. Existing explicit SQL workspace filtering and API
authorization remain defense in depth, not replacements for RLS.

The existing tenant transaction applies parameterized `set_config(..., true)`
for workspace/user and clears unrelated invitation/recovery capabilities. No new
session-global defaults or context variables were introduced. Commit/rollback
and pool isolation use the existing transaction-local mechanism. SQLite runs the
same application checks without PostgreSQL setting SQL.

## RLS activation and command permissions

Newly activated table: **`organization_human_role_assignments` only**.

The previous ten remain enabled/forced: `simulations`, `tasks`,
`agent_executions`, `agent_messages`, `activity_events`, `run_events`,
`simulation_metrics`, `simulation_uploads`, `workspaces`,
`organization_memberships`. Total active: **11**. `uploads` is still excluded
from declared/active RLS because it lacks explicit tenant/user ownership;
an empty `DEFERRED_RLS_TABLES` set does not mean upload isolation is solved.

Two reviewed policies protect HR assignments:

- `fm_tenant_isolation` (`FOR SELECT`): an active organization and active actor
  membership are required. Owner/Admin can read that organization's assignments,
  including inactive history; Member can read only their own active assignments.
- `fm_tenant_isolation_write` (`FOR ALL`): only active Owner/Admin membership in
  the selected organization permits modifying rows. The resulting row must be
  attributed to the current actor. Active assignments require an active target
  membership in the same organization; inactive rows may be retained for cleanup.

Separating the read policy from the management policy prevents a Member's own-
role visibility from granting `DELETE`/`UPDATE` rights. The managerial policy's
additional SELECT allowance is a subset of the read policy's managerial access.
This uses PostgreSQL's command-specific policy rules, not database bypass roles.
See [PostgreSQL CREATE POLICY](https://www.postgresql.org/docs/current/sql-createpolicy.html).

Missing user/workspace context, user-only bootstrap context, inactive organization,
inactive actor membership and Personal Workspace match no HR rows. A wrongly
selected foreign organization without active IAM membership also matches none.
Policy subqueries read workspaces/memberships; neither policy reads HR assignments
back, avoiding recursive RLS expansion.

Startup refresh recognizes these two policy names **only on this table**. Unknown
policies still fail readiness preflight before policy DDL. Initialization retains
the existing unsafe-role rejection (`SUPERUSER`, `BYPASSRLS`, or membership in a
bypass-capable role), `FORCE RLS`, and transactional policy replacement. No
unrestricted application connection or destructive record migration was added.

## IAM versus HR-domain permissions

IAM Owner/Admin/Member and HR Recruiter/Reviewer/Approver remain separate.
HR permissions cannot create organization visibility, confer IAM administration,
promote ownership, or broaden another organization's rights. An Admin can assign
HR responsibilities within their organization but remains subject to existing IAM
role-change constraints. Ordinary Member cannot manage assignments/self-promote.

HR resolution rereads active assignments and memberships; deactivated assignments
and inactive memberships do not survive as cached grants. A membership revoked
between bootstrap and scoped read returns empty HR authorization. Unexpected
storage failures are propagated, not hidden as missing roles. As with normal
database transactions, this does not retroactively cancel operations already
completed or promise revocation beyond the transaction's visibility rules.

Personal Workspace has no HR-domain authorization even if a malformed legacy
SQLite row exists. Historical assignment rows are not deleted to revoke access.
Existing API inaccessible-workspace 404 and insufficient-permission 403 behavior
is preserved. HR listing also rechecks this distinction after preflight revocation.

## Adversarial validation

Deterministic tests cover actor/target distinction, scoped reads/writes, cross-org
isolation, Member self-promotion denial, Admin IAM limits, assignment/membership
revocation, Personal Workspace denial, missing context, actor forgery predicates,
inactive-target cleanup, stale preflight demotion, rollback, API status behavior,
and PostgreSQL no-actor rejection before checkout.

The new opt-in PostgreSQL suite adds nine cases for actual ENABLE/FORCE flags,
command policies, unrestricted-query isolation, raw Member write denial, actor
forgery/cross-org writes, revocation, Personal Workspace rejection, same-connection
commit/rollback context clearing and rollback durability. It reuses the existing
isolated local-schema fixture requiring `TENANT_TEST_DATABASE_URL` and a normal
`NOSUPERUSER NOBYPASSRLS` schema-creating login. It never uses production
`DATABASE_URL`; each test removes only its uniquely generated disposable schema.

Local validation (2026-10-05):

- Focused HR/RLS/context/recovery suite: **78 passed, 25 skipped**.
- Full `pytest` suite: **369 passed, 25 skipped** (394 collected).
- Backend compile: passed (`python -m compileall -q backend`, project virtualenv).
- `git diff --check`: passed.
- One existing warning: Starlette TestClient references AnyIO's deprecated
  `anyio.abc.BlockingPortal` alias.
- All 25 skips require unconfigured `TENANT_TEST_DATABASE_URL`: six data-plane,
  ten bootstrap and nine HR-role enforcement cases. PostgreSQL enforcement,
  same-pool commit/rollback isolation and production activation are **not verified**
  by this run. SQLite predicate checks are not a substitute for those tests.
- Provider/Groq calls: **0**. No frontend, production data or deployment changes.

## Remaining Phase 4.5 blockers and workflow

NOT IMPLEMENTED in this checkpoint: 4.5.5C upload ownership/schema and tenant-scoped
upload API/RLS. PARTIAL: 4.5.6 final adversarial and live PostgreSQL enforcement
verification, including previous data-plane/bootstrap cases and these HR cases.
Do not proceed to Phase 4.6 until these gates are satisfied.

The latest workflow permits a local commit after this subphase is validated;
GitHub push remains prohibited until the entire major Phase 4 is complete. Older
checkpoint workflow notes are historical. No commit/push is performed here.
