# Phase 7 — Human review, revision and approval

Phase 7 extends the organization HR foundation with authenticated human decisions
on exact saved JD revisions. It adds no publication, candidate workflow, provider,
or production LangGraph activation. Task and StageExecution remain the AI execution
authority; ExecutionContext, RoutePlan, GraphRunState and all six system IDs are unchanged.

## Workflow

The foundation JD lifecycle remains `draft → archived`. Review status belongs to
an immutable **submission**, not the editable JD head. An unsubmitted JD is a draft.
A submission binds organization, JD ID/revision, requesting actor, UTC timestamp,
and optional explicitly associated completed AI run IDs. Its requirement and
optional knowledge revisions are the exact relational sources of the immutable JD
revision, returned with their original snapshots. Submission never changes content.

| Previous state | Human action | New state | Required permission |
| --- | --- | --- | --- |
| draft / unsubmitted revision | submit | pending_review | JD_DRAFT_EDIT |
| pending_review | recommend | reviewed | JD_REVIEW |
| pending_review | request_changes | changes_requested | JD_REQUEST_REVISION |
| pending_review | reject | rejected | JD_REJECT |
| reviewed | approve | approved | JD_APPROVE |
| reviewed | reject | rejected | JD_APPROVE and JD_REJECT |
| reviewed | request_changes | changes_requested | JD_APPROVE and JD_REQUEST_REVISION |

The UI labels `reviewed` as **Awaiting approval**. `approved`, `rejected` and
`changes_requested` are terminal for that submission. There is no same-state
rewrite, repeat decision, withdrawal or automatic rewrite. A human edits the JD
through the existing `expectedRevision` contract, then submits the new revision
using the same submission endpoint. Each JD revision can be submitted once.

Editing or archiving the JD marks earlier submissions `stale` in the response.
This is a derived eligibility flag, not a rewritten historical decision. Stale
requests accept no further decisions. A historical approval remains approval of
its original revision and never transfers to the new revision. Changes to source
heads do not alter the pinned source revisions or invalidate their historical use.
A newer revision may be submitted even if the older request was still pending;
the older request is stale and its authentic recorded state remains visible.

## Human authority

The existing central `security/hr_roles.py` policy is the source of truth:

- Recruiter: author/edit the JD, submit, revise and resubmit; read decisions.
- Reviewer: read, recommend and request changes. No rejection or final approval
  grant exists in the established Reviewer role.
- Approver: read/review/recommend, reject and finally approve. The existing
  Approver role includes JD_REVIEW, so it can also perform the review step.
- A person holding both Reviewer and Approver can request changes at final approval.

No inspected Phase 4–6 requirement mandates distinct people for submission,
review and approval. Phase 7 preserves authorized combined-role behavior rather
than introducing an unsupported separation-of-duties restriction. Browser acceptance
also exercises three distinct people. IAM Owner/Admin alone grants no HR authority.
Every repository operation rechecks active user, organization, membership and HR
roles in the tenant transaction. Final decisions require the approver permission
in addition to the action permission, including in PostgreSQL RLS. HR roles do not
grant membership or IAM administration. Personal Workspaces have no review workflow.
Session authentication and existing 401/403/404 distinctions are unchanged.

## Persistence, migration and concurrency

Operational schema **13** is additive to 12. Initialization creates new tables,
updates the relational marker and SQLite PRAGMA, installs guards, and refreshes
reviewed PostgreSQL policies under the existing startup advisory lock. Earlier
supported migrations still run. No existing HR or execution records are rewritten.

- `hr_review_submissions`: stable ID, workspace, JD ID/revision, authenticated
  requester, timestamp and original AI run references. Composite FK binds the
  JD revision in the same workspace. A unique constraint permits one submission
  per workspace/JD/revision. The JD revision already has composite foreign keys
  to its exact requirement and optional knowledge revisions.
- `hr_review_events`: stable event ID, tenant-composite submission FK, monotonic
  version, authenticated actor, timestamp, action, from/to states and bounded notes.
  Unique submission/version and explicit state/action/version checks reject
  duplicate and invalid transitions. Decisions require nonblank notes.

Both tables are append-only. SQLite denies UPDATE/DELETE with triggers. PostgreSQL
has SELECT and INSERT policies only, and ENABLE/FORCE RLS. Policy predicates
independently check active organization/user/member and appropriate live HR grants;
insert actor fields must equal the trusted transaction principal. No tenant context,
foreign workspace, revoked grants or Personal Workspace exposes these rows.

Database insertion guards validate current JD revision/status and the actual
previous persisted event; an approval cannot skip a recommendation. Application
submission/decision/edit transactions share a PostgreSQL transaction advisory lock
key derived from the JD ID. Review insertion triggers also serialize decisions.
SQLite uses BEGIN IMMEDIATE for review mutations and JD edits. PostgreSQL decisions
reload evidence and live authorization after acquiring the lock. `expectedVersion`
is mandatory for each human decision. A competing decision or stale JD returns
409 without a partial event. Operational connection failures are not disguised as
workflow conflicts; only integrity, lock/deadlock and serialization conflicts map
that way. Two-connection PostgreSQL races cover both competing reviews and final
approval against a JD edit.

## APIs

All paths are under authenticated `/api/v1/hiring`, with the session cookie and
`X-Workspace-Id` resolved by the existing workspace access layer:

- `GET /reviews/capabilities`: live submit/action capabilities.
- `POST /reviews`: `{jobDescription: {id, revision}, aiRunIds: []}`; returns 201.
- `GET /reviews`: tenant-scoped current and historical submissions with snapshots.
- `GET /reviews/{id}`: exact submitted JD and sources, history, status/version/stale.
- `GET /reviews/{id}/history`: genuine persisted transition events in version order.
- `POST /reviews/{id}/review`: recommendation, change request or authorized rejection.
- `POST /reviews/{id}/approval`: eligible reviewed request, authorized final decision.

Decision bodies are `{expectedVersion, decision, notes}`. Unknown fields, supplied
actors/ownership/status, nonpositive/bool versions and invalid action names are 422.
Inaccessible workspace/record/evidence is 404, insufficient HR authority is 403,
anonymous/revoked session is 401, and invalid/stale transitions are 409. Accessible
Personal Workspaces are 403. No client field can impersonate a human or AI approver.

## AI proposals and frontend

Optional run associations are checked against actual completed Phase 6 HR tasks
in the same workspace. Source requirement/knowledge references must exactly match
the submitted JD; validation also must match the JD revision. Missing, foreign,
failed, duplicated and mismatched evidence is rejected. Original Task and stage
outputs, source fingerprints, agent ID and run identity are preserved. No results
are copied into a duplicate evidence table. Soft-deleted runs retain their IDs;
restoration through the existing Recycle Bin makes their evidence inspectable again.

The HR Hiring page adds submit controls, pending/history filtering, immutable JD
and source snapshots, action forms, actor/time/notes history, and a route back to
the existing JD editor after changes/rejection. Matching AI runs can be explicitly
associated and inspected beside the JD. Use Reload review requests to refresh
assistance choices after executing a new AI run. An association is evidence linkage,
not an adoption or approval claim. There is no automatic or one-click AI adoption;
human changes remain deliberate edits attributed by existing JD revision history.

Workspace switching remounts the HR page; cancellation/generation guards discard
obsolete list/detail/decision responses. Controls follow live backend capabilities;
the backend remains authoritative after revocation. Loading, API errors and stale
conflicts are visible, with explicit reload. No unrelated screens were rebuilt.

## Acceptance and external gates

See [PHASE7_ACCEPTANCE_REPORT.md](PHASE7_ACCEPTANCE_REPORT.md) for exact results,
browser evidence and local infrastructure cleanup. The localhost fixture
`backend/tests/hr_reviews_browser_fixture.py` uses disposable SQLite data, separate
human sessions and an explicitly test-only deterministic provider adapter. Never
import it into production or expose its session routes outside localhost.

Real Google/Groq integration, production migration/runtime-role checks, deployment
and production graph activation remain separate unverified gates. Phase 7 local
acceptance does not authorize them or start Phase 8.
