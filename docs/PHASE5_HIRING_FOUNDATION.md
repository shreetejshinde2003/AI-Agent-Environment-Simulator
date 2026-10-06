# Phase 5 — HR Hiring Foundation

Phase 5 adds organization-owned hiring requirements, private role knowledge and
human-authored job description drafts. It does not execute HR agents, approve or
publish descriptions, screen candidates, or make employment decisions. Existing
Task, StageExecution, ExecutionContext, RoutePlan and GraphRunState contracts are
unchanged. The six system agents and revisioned custom Agent Builder remain intact.
LangGraph stays disabled by default. Phase 6–8 workflows remain future work.

## Domain and lifecycle

Requirements capture position title, department, hiring purpose, responsibilities,
required/preferred skills, experience, qualifications, location, employment
arrangement, openings and constraints. Only title and purpose are mandatory;
openings default to one. No salary or candidate data is invented.

Role knowledge captures title, responsibilities, skills, experience,
qualifications, competencies, terminology and evaluation criteria. It is private
to its owning organization, with full revision history.

Job descriptions capture title, summary, responsibilities, skills, experience and
qualifications. A source requirement revision is mandatory; one role-knowledge
revision is optional. These are explicitly human-authored records: there is no AI
provenance claim, provider call or automatic content generation.

| Entity | Initial state | Allowed state changes |
| --- | --- | --- |
| Requirement | draft | draft → active or archived; active → closed or archived; closed → archived |
| Role knowledge | active | active → archived |
| Job description | draft | draft → archived |

Same-state edits are allowed until archival, including corrections to closed
requirements; reopening is not allowed. Archived records and all historical
revisions are read-only. There are no deletion endpoints. New descriptions cannot
use currently closed or archived sources. Existing descriptions retain their
historical sources and can still be edited if a source is subsequently archived.
A human can deliberately select another source revision on a later description
revision; the old description revision retains its original references.

All edits use `expectedRevision`. A stale edit returns 409 and leaves the record
and history intact. Each successful edit, including a lifecycle change, appends
a revision with authenticated actor and UTC timestamp.

## Database and migrations

Operational schema version **12** is additive to version 11. Existing startup
initialization uses SQLAlchemy `create_all`, the established older-schema column
migrations, and the PostgreSQL transaction advisory lock. It then updates the
schema marker. SQLite also updates `PRAGMA user_version`. Repeated initialization
is safe. Existing runtime databases are migrated on application initialization;
acceptance uses disposable databases and schemas.

Six tables are added:

- `hr_requirements`, `hr_requirements_revisions`
- `hr_role_knowledge`, `hr_role_knowledge_revisions`
- `hr_job_descriptions`, `hr_job_descriptions_revisions`

Heads have stable IDs, workspace ownership, current revision/status and original
creation attribution. History has structured JSON content, update attribution and
revision numbers. Indexes cover workspace listing and revision lookup. Foreign
keys use RESTRICT; workspace IDs and actor IDs reference existing platform tables.
Positive revision and lifecycle checks are database constraints.

Description history includes relational requirement/knowledge IDs and revision
numbers. Composite foreign keys include workspace ID, preventing foreign-tenant
sources even when both IDs exist. Optional knowledge ID/revision must be supplied
together. Changing a source record does not change an existing description.
SQLite triggers deny UPDATE/DELETE on HR histories. PostgreSQL revisions have
SELECT and INSERT policies only; no UPDATE/DELETE policy is granted.

All six tables are included in the central tenant-isolation inventory and the
explicit startup RLS activation allowlist. PostgreSQL initialization enables and
forces RLS. It continues to reject bypass-capable credentials or unreviewed
policies. No existing simulation, upload, agent or checkpoint records are rewritten
by the Phase 5 schema change.

## Security policy

Workspace IAM remains the maximum authority: an active authenticated user, active
organization and active owner/admin/member membership are required. Personal
workspaces have no hiring semantics. No HR role grants membership or IAM management.

| Active HR human role | Read records/history | Requirements | Role knowledge | Description drafts |
| --- | --- | --- | --- | --- |
| Recruiter | yes | create/edit/lifecycle | create/edit/archive | create/edit/archive |
| Reviewer | yes | read only | read only | read only |
| Approver | yes | read only | read only | read only |
| No HR role | no | no | no | no |

Owner/admin IAM alone does not grant HR-domain access. Owners/admins assign human
roles through existing organization administration. A member with an explicit
Recruiter role can edit HR data without gaining Agent Builder, member management
or other IAM authority. Role-knowledge management is an explicit Recruiter
permission added to the existing central HR role map.

The repository rechecks live IAM and HR roles inside each tenant transaction.
PostgreSQL RLS independently checks active user, active organization, recognized
active membership and active HR assignments, using the same central permission
map. Read and write grants are separate; revision insert attribution must match
the current principal. Client workspace/record/source IDs are scoped identifiers,
never grants. Revoked membership or HR roles deny subsequent requests and SQL
queries. Missing database tenant context exposes no HR records.

Existing response semantics apply: anonymous access is 401; inaccessible
workspaces/records/sources are 404; accessible workspaces with insufficient HR
permissions are 403; malformed bodies are 422; stale revisions or forbidden
lifecycle changes are 409.

## API and frontend

Under `/api/v1/hiring`:

- `GET /capabilities` returns live view and write capabilities for the current user.
- `/requirements`, `/role-knowledge`, `/job-descriptions` each support GET list,
  POST create, GET `/{id}`, PUT `/{id}`, GET `/{id}/revisions`.

The existing session cookie and `X-Workspace-Id` apply. Missing workspace selection
uses the existing Personal Workspace default and is denied for HR. Python model
fields are snake_case; API JSON uses CamelModel camelCase. Unknown fields and
invalid states are rejected, including client ownership, approval or provenance
claims. Text/list/opening limits are enforced on both frontend and backend.

HR Hiring appears in the existing navigation. Its three sections provide real
create/edit/detail forms, lifecycle controls, revision history and source revision
selection. Capabilities come from the backend rather than cached workspace role
labels. Workspace changes remount the HR view, clear forms/history and cancel list
requests; obsolete detail responses are discarded. Loading, errors, reload,
permission denial and read-only states are explicit. Simulation run controls are
not displayed inside the HR page.

## Acceptance and local infrastructure

See `PHASE5_ACCEPTANCE_REPORT.md` for exact consolidated counts and browser evidence.
Tests do not call paid providers. PostgreSQL uses `TENANT_TEST_DATABASE_URL` with
the existing fixture's random schemas. Checkpoint regression tests additionally
accept `CHECKPOINT_TEST_SCHEMA` so a separate restricted runtime login can use an
isolated FORCE RLS schema, without reading existing checkpoint data. Existing
checkpoint table-owner and runtime-role separation remains mandatory.

The browser fixture `backend/tests/hiring_browser_fixture.py` creates a disposable
SQLite database and local session; its provider adapter raises if invoked. It is
never imported by production. Stop the fixture after acceptance to remove its
temporary data. Do not expose its session endpoint outside localhost.

Production gates are unchanged: actual deployment/runtime role and migration
checks, real Google/Groq integration, and production graph activation acceptance
remain unresolved. Phase 5 is not production deployment approval. Future HR
agents may consume pinned source revisions through the established execution
contracts; human approval remains a separate future authority boundary.
