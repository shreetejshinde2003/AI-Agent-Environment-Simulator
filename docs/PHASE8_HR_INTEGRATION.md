# Phase 8 — integrated HR application

HR Hiring is one organization-scoped workspace with four navigation choices:
Hiring workflow, Source records and drafts, AI assistance, and Human review and
approval. All data comes from the existing authenticated Phase 5–7 APIs and their
immutable revisions, Task/StageExecution evidence, submissions and decision events.

## Journey and authority

Recruiters create requirements and organization role knowledge, then deliberately
create and edit human JD drafts with exact source revisions. A requirement can
open a blank human JD with its selected revision prefilled. No content is generated
or adopted by that action. Existing lifecycle restrictions remain authoritative.
Historical revisions are inspectable but cannot be edited.

The workflow overview shows requirements and current JDs, pinned source links,
human editor/time, source-matching completed AI evidence, submission history and
an eligible next action. A new revision after an earlier submission needs its own
submission. Earlier approvals remain explicitly attributed to their own revision.
Document lifecycle status never substitutes for persisted review status.

AI actions open with the selected saved references. Requirement assessment and JD
proposal require existing authoring permission; validation requires existing
review permission. Users can select another exact revision in the existing picker.
Proposals show original run ID, status, errors, structured output, source
fingerprints, provider/model and recorded stage telemetry. Source buttons return
to the exact saved revisions. Source matching establishes relevance, not adoption;
only the user's explicit submission association establishes an AI-to-review link.
Failed and historical runs remain separately inspectable in related run history.

A saved eligible JD opens the submission form. Completed matching evidence can be
explicitly associated. Reviewers can inspect pinned snapshots, recommend or
request changes as allowed by Phase 7. Approvers can make only the eligible
approval-stage decisions their existing permission map allows. A confirmation
dialog shows decision, revision, submission and notes before the immutable write.
It reuses the existing accessible modal, including inert background, contained
Tab focus, Escape cancellation and focus restoration. Confirmation captures the
expected version; backend concurrency checks remain authoritative.

Recruiters follow feedback to the existing versioned human editor, save a new
revision and submit it separately. Historical JD/source inspections cannot acquire
current-revision submission or decision actions. Approval never transfers forward.
Combined responsibilities are supported; IAM ownership/Admin status alone confers
no HR authority. Admin membership now uses the existing shared IAM label correctly.
Personal Workspaces display only the organization-selection explanation.

## Exact historical source usage

Two read-only routes close the historical relationship gap:

- `GET /api/v1/hiring/requirements/{id}/revisions/{revision}/job-descriptions`
- `GET /api/v1/hiring/role-knowledge/{id}/revisions/{revision}/job-descriptions`

Both return `list[HRRecord]` from existing immutable JD revision rows, including
historical revisions whose current JD head uses another source. They validate the
root source revision and effective HR view permission inside the existing tenant
transaction. Queries scope both root and related rows to the workspace and use
exact stored source ID/revision columns. Foreign or unavailable roots return 404;
revoked HR authority returns 403 (inaccessible workspace follows existing 404
semantics). No additional storage, migrations, permissions or state machine exists.

Source detail views distinguish exact JD usage from the broader related AI run
history, whose entries explicitly identify their recorded source revisions.

## Refresh, switching and errors

The workspace read projection uses a single captured workspace ID and shared
abort signal. Reads run in groups of at most three to bound connection pressure.
No partial projection is published when a read fails. This is a UI projection of
existing reads, not a new transactional snapshot API; concurrent changes remain
subject to backend revision/version checks.

Mutation acknowledgement updates the saved record; refreshing then retrieves
current records, permissions, runs and reviews. An explicit Refresh hiring
workspace action retrieves changes from other sessions. Decision notes survive
refresh; a chosen action must still be eligible. Optional AI choices clear when
the selected JD revision changes. Read/loading, empty, permission-denied and
network/conflict states remain visible with explicit recovery actions.

Changing workspace remounts the entire HR subtree. Its old projection, forms,
source choices, review details, run selection and polling are discarded. Cleanup
aborts list/relationship reads and invalidates late detail responses; unmounted
children cannot publish old results into the next workspace. Authorization errors
from actions trigger a fresh capability read. Visibility supplements, but never
replaces, backend IAM, HR permissions and FORCE RLS.

## Boundaries

Operational schema stays 13. No second JD/review/evidence system, new execution
engine, approval inheritance, publication, production provider call, deployment,
Railway change, production graph activation, or Phase 9/10 work is included.
Existing list APIs return complete histories; pagination remains a future scaling
concern. Live provider and production infrastructure verification remain separate
release gates. Local acceptance is recorded in PHASE8_ACCEPTANCE_REPORT.md.
