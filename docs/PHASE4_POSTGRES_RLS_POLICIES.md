# Phase 4.5.3 — PostgreSQL Row-Level Security Policies

Historical policy-definition checkpoint. The current local 4.5.5A refinement
activates workspace/membership bootstrap alongside the existing eight data-plane
tables, with user-bound discovery and bounded invitation/recovery capabilities.
See [current bootstrap behavior](PHASE4_WORKSPACE_BOOTSTRAP_RLS.md); HR-role and
upload hardening remain deferred, and live PostgreSQL verification remains partial.

## Purpose

This checkpoint defines the database-level workspace boundary that will sit below
API authorization and repository scoping. PostgreSQL RLS is defense in depth: an
application query that accidentally omits a workspace predicate must still be
unable to cross tenant boundaries.

## Policy source of truth

`app.security.tenant_isolation.TABLE_ISOLATION_RULES` remains the inventory.
`app.security.postgres_rls` translates the workspace-owned portions of that
inventory into PostgreSQL policy DDL.

The policies read only transaction-local values created by Phase 4.5.2:

- `app.current_workspace_id`
- `app.current_user_id`

Missing settings resolve to `NULL`; no policy supplies a fallback workspace.

## Protected tables

Direct/root policies cover:

- `workspaces`
- `organization_memberships`
- `organization_human_role_assignments`
- `simulations`

Simulation-derived policies cover:

- `tasks`
- `agent_executions`
- `agent_messages`
- `activity_events`
- `run_events`
- `simulation_metrics`
- `simulation_uploads`

Each simulation-derived policy verifies ownership by joining to `simulations`
and comparing that parent row's `workspace_id` with the trusted transaction
workspace.

## Bootstrap access

Workspace discovery occurs before a workspace can be selected. Therefore:

- a user may see their Personal Workspace through `personal_owner_user_id`;
- a user may see organization workspaces for which they have an active
  membership;
- a user may read their own membership rows;
- membership writes remain selected-workspace scoped.

This is why Phase 4.5.2 carries both user and workspace identity.

## Upload exception

`uploads` remains intentionally outside the RLS policy set. Phase 4.5.1 found
that an upload may exist before being linked to a simulation and currently has
neither `workspace_id` nor `owner_user_id`. Enabling a guessed policy would give
a false sense of isolation. A later Phase 4.5 hardening checkpoint must add
explicit ownership first.

## ENABLE and FORCE

Every protected table receives both:

```sql
ALTER TABLE ... ENABLE ROW LEVEL SECURITY;
ALTER TABLE ... FORCE ROW LEVEL SECURITY;
```

`FORCE` ensures the table owner is also subject to policies. The production
runtime database role must additionally not be a PostgreSQL superuser and must
not have `BYPASSRLS`, because those privileges can bypass RLS regardless of
policy definitions.

## Activation sequencing

The installer is deliberately **not** called from repository initialization in
this checkpoint. Existing repository methods still open ordinary transactions
without applying Phase 4.5.2 tenant context. Enabling FORCE RLS immediately
would therefore block legitimate application access.

Phase 4.5.4 must first move tenant-owned repository reads/writes onto trusted
context-bearing transactions. Only after that wiring is verified should startup
or migration activation call `install_postgres_rls_policies(...)`.

This sequencing keeps the deployment fail-closed without breaking the current
application between commits.

### Phase 4.5.4C update

The section above records Phase 4.5.3's historical sequencing. Startup now uses
**`install_data_plane_rls_policies(...)`**, not the full-set installer. Only
`simulations` and its seven child tables are automatically activated after
readiness preflight. Bootstrap/membership/HR-role policies remain definitions;
uploads still require schema hardening. See
[data-plane activation and recovery](PHASE4_DATA_PLANE_RLS_ACTIVATION.md) for
runtime role requirements, deferred boundaries, recovery, and validation limits.
