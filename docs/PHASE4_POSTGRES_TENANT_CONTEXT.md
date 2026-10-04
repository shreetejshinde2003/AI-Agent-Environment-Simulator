# Phase 4.5.2 — Trusted PostgreSQL tenant session context

## Purpose

Phase 4.5.2 carries an already-authenticated and already-authorized application
identity into one PostgreSQL transaction.  It does **not** replace API RBAC,
workspace resolution, or repository scoping.  It is the trusted input that
Phase 4.5.3 RLS policies will consume.

## Database settings

Each PostgreSQL tenant transaction sets:

- `app.current_workspace_id`
- `app.current_user_id`

The implementation uses PostgreSQL `set_config(name, value, true)`.  The third
argument is `true`, so both values are transaction-local.  A connection returned
to the pool therefore cannot retain one request's tenant identity for a later
request.

The values are passed as SQL parameters rather than interpolated into SQL.

## Fail-closed contract

A tenant transaction cannot be opened with a missing, whitespace-padded, NUL-
containing, or oversized workspace/user identifier.

RLS policies must read tenant context with:

```sql
NULLIF(current_setting('app.current_workspace_id', true), '')
NULLIF(current_setting('app.current_user_id', true), '')
```

`current_setting(..., true)` returns `NULL` when the setting is absent.  Direct
comparisons against a tenant column therefore do not match rows when no trusted
context was installed.  Policies must not use fallback/default tenant IDs.

## Trust boundary

`tenant_transaction(...)` accepts trusted identifiers only.  Callers must obtain
them from authenticated workspace resolution/RBAC and must never pass a raw
`X-Workspace-Id`, URL parameter, or other client value without authorization.

## SQLite compatibility

SQLite validates the same context values but does not receive custom database
session settings.  Existing local development and tests therefore remain usable.
PostgreSQL RLS remains the production defense-in-depth layer.

## Next checkpoint

Phase 4.5.3 will use these settings to build PostgreSQL RLS policies for the
currently classifiable tenant-owned tables.  Tables flagged by the 4.5.1 audit as
requiring schema hardening (notably unattached uploads) must be fixed before they
can receive complete RLS protection.
