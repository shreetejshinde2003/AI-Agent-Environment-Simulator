# Phase 4.5 Tenant-Isolation Contract

## Purpose

Phase 4.5 adds database-level defense in depth without replacing the application protections already established in Phases 4.2–4.4. The required stack is:

1. authenticated application session;
2. workspace resolution and RBAC;
3. repository-level tenant scoping;
4. PostgreSQL transaction context;
5. PostgreSQL Row-Level Security (RLS).

A failure at one layer must not silently expose another workspace's business data.

## Persisted-data classification

| Table | Classification | Tenant derivation |
| --- | --- | --- |
| `schema_version` | system-global | migration metadata |
| `users` | identity | authenticated user |
| `auth_sessions` | identity | `user_id -> users` |
| `workspaces` | workspace root | `id` |
| `organization_memberships` | tenant-direct | `workspace_id` |
| `organization_human_role_assignments` | tenant-direct | `workspace_id` |
| `dataset_registry` | system-global | shared benchmark registry |
| `simulations` | tenant-direct | `workspace_id` |
| `tasks` | tenant-via-simulation | `simulation_id -> simulations.workspace_id` |
| `agent_executions` | tenant-via-simulation | `simulation_id -> simulations.workspace_id` |
| `agent_messages` | tenant-via-simulation | `simulation_id -> simulations.workspace_id` |
| `activity_events` | tenant-via-simulation | `simulation_id -> simulations.workspace_id` |
| `run_events` | tenant-via-simulation | `simulation_id -> simulations.workspace_id` |
| `simulation_metrics` | tenant-via-simulation | `simulation_id -> simulations.workspace_id` |
| `simulation_uploads` | tenant-via-simulation | `simulation_id -> simulations.workspace_id` |
| `uploads` | schema hardening required | no tenant/owner column yet |
| `agent_roster` | system-global | shared platform metadata |

The executable copy of this inventory lives in `app.security.tenant_isolation`; tests fail if a future persisted table is added without an isolation classification.

## RLS contract

PostgreSQL policies must fail closed when tenant context is absent or invalid. Application code must never use RLS as a substitute for API authorization.

For a request operating inside a selected workspace, the transaction context will eventually carry both the authenticated user and resolved workspace. Direct tenant tables may compare their `workspace_id` to that context. Simulation-derived tables must authorize through an `EXISTS` relationship to the owning simulation rather than trusting client-supplied IDs.

Personal Workspaces remain private to `personal_owner_user_id`. Organization access requires an active organization membership. HR-domain roles never expand raw tenant visibility beyond the IAM membership boundary.

## Audit findings that block immediate RLS completion

### 1. Upload ownership is not representable yet

`uploads` can be persisted before a simulation is created. The row currently has neither `workspace_id` nor `owner_user_id`, so an orphan upload cannot be safely assigned to a tenant by PostgreSQL policy. Phase 4.5 must add explicit upload ownership before enabling strict RLS for this table.

The current upload API also reads uploads by ID without workspace scoping. This must be hardened together with the schema change.

### 2. Some agent statistics still aggregate global simulation history

The agent metadata/statistics routes use the repository's global simulation list for runtime statistics. That is acceptable only for truly system-global metadata; per-run counts, token totals, timestamps, model names, and output previews are tenant-derived and must be scoped to the selected workspace before Phase 4.5 can be declared complete.

### 3. Unscoped repository methods remain compatibility primitives

`repository.get()` and `repository.list()` predate tenancy. Workspace-facing routes must use scoped alternatives. Later Phase 4.5 checkpoints should either constrain these methods to trusted internal/system use or introduce explicit fail-closed tenant context so a new route cannot accidentally call them and bypass workspace filtering.

## Non-goals for 4.5.1

This checkpoint does not enable RLS, change SQL transaction context, migrate upload ownership, or alter runtime API behavior. It establishes the complete persisted-data boundary and records the known gaps that the following 4.5 checkpoints must close.
