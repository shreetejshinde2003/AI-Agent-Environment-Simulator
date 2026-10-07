# Phase 8 manual browser acceptance — 7 October 2026 (Asia/Kolkata)

27 checkpoints passed, 0 remaining failed, 0 skipped. These are manual browser
checkpoints, separate from the automated backend/frontend test counts.

Real React/Vite at 127.0.0.1:5179 and real authenticated FastAPI at 127.0.0.1:8019.
Disposable SQLite and six distinct test-only human sessions; deterministic provider
fixtures only. No production decisions or live provider calls.

| # | Checkpoint | Result |
| --- | --- | --- |
| 1 | Personal Workspace excludes active HR functionality | Pass |
| 2 | Organization opens coherent workflow/navigation and real requirement status | Pass |
| 3 | Requirement revision 1 remains read-only while its head is revision 2 | Pass |
| 4 | Requirement-to-human-JD creation pins requirement 1 and selected knowledge 2 | Pass |
| 5 | JD proposal retains structured output, fingerprints and stage evidence without adoption | Pass |
| 6 | Requirement analysis completes through the final integrated workflow | Pass |
| 7 | Provider failure remains a failed persisted run without successful output | Pass |
| 8 | Explicit submission associates matching original AI evidence with exact JD revision | Pass |
| 9 | Reviewer-only user validates saved JD with its pinned sources | Pass |
| 10 | Reviewer-only change request has no approve/reject control | Pass |
| 11 | Confirmation cancellation leaves persisted submission pending | Pass |
| 12 | Recruiter follows feedback, saves human revision 2 and resubmits | Pass |
| 13 | Reviewer recommends revision 2 and cannot make its approval-stage decision | Pass |
| 14 | Approver-only user sees eligible approve/reject, without change-request privilege | Pass |
| 15 | Explicit approval history contains separate recruiter/reviewer/approver identities and times | Pass |
| 16 | Reload retrieves persisted approval and pinned submitted content | Pass |
| 17 | Newer human revision displays its own submission requirement and earlier approval only | Pass |
| 18 | Combined-role recommendation/rejection preserves earlier revision approval | Pass |
| 19 | Knowledge head advances to revision 3 while JD retains read-only source revision 2 | Pass |
| 20 | Workspace switching with delayed old revision read clears old JD/source/evidence data | Pass |
| 21 | IAM-only Owner has no HR workflow authority | Pass |
| 22 | IAM-only Admin retains correct Admin label and has no HR authority | Pass |
| 23 | Member without HR role has no active HR records or controls | Pass |
| 24 | Combined-role user has authoring/AI/review actions and decision notes survive refresh | Pass |
| 25 | Native modal contains Tab focus; Escape cancels, restores trigger and preserves notes | Pass |
| 26 | Narrow layout at measured CSS width 400 has document/main scroll widths equal to client widths | Pass |
| 27 | Exact source usage finds historical JD after source changes; knowledge revision finds both JD revisions | Pass |

An initial browser scenario covered changes/revision/resubmission, proposal,
validation, approval and rejection. The API fixture was then restarted with the
historical lookup routes, and the final-build journey was repeated through
analysis, submission, distinct reviewer recommendation, distinct approver approval,
new source-bound revision, historical requirement/knowledge usage, keyboard
confirmation and workspace-switch cleanup.

During development the native JavaScript confirmation stalled in the in-app
browser; it was replaced with the existing accessible application modal. A fast
submission/refresh interaction exposed clearing decision notes, which was fixed
and verified by explicit refresh before recording the preserved recommendation.
Local fetch failures surfaced honestly and recovered through Reload, retrieving
persisted decisions without fabricating success or repeating the decision. Reads
were bounded to at most three concurrent requests; the final repeated journey
completed without a fetch failure. A development HMR dependency-array warning
was absent from the final reloaded build. Responsive viewport override was reset.

Screenshots: phase8-approved-history.jpg, phase8-newer-revision.jpg,
phase8-responsive.jpg, phase8-final-approval.jpg,
phase8-historical-source-usage.jpg and phase8-knowledge-usage.jpg in
../screenshots/. Both test servers were stopped and their disposable data removed.
