# Limited overnight QA — 2026-10-10

Starting HEAD: `26c5755d28dd342fc48337c66ada1a432099857f`, existing local `main`. One focused code/evidence pass; no broad redesign. End commit is the commit containing this report.

## Inspection and corrections

Reviewed the final local acceptance report and per-check evidence, Organizations/member-management guidance, Research sample/saved-trial controls, Hiring's capability gate and workflow, current custom-agent lifecycle corrections and polling status logic. The prior 232 frontend/52 backend/6 PostgreSQL/42 browser results remain historical evidence; they were not repeated overnight.

Two confirmed UI gaps corrected:

1. **Missing HR responsibility:** the denied view offered only a short message. It had no direct navigation or access recheck after a manager granted a role. Added a visible heading, exact Organizations → Member management → Hiring responsibilities instructions, Owner/Admin versus HR separation, an Open Organizations action and a Check HR access again action using the existing authenticated capability loader. Rechecks disable while pending; no record requests or authoring controls are introduced when HR view capability is denied. The owner's successful HR-role assignment is consistent with the existing permission gate, not an unexplained outage.
2. **Research evidence loading:** Open run evidence was enabled with no fetched Task, while its handler did nothing. It is now disabled until the saved Task exists and while a foreground operation is pending. The existing loading explanation and exact-workspace evidence navigation remain intact.

No additional high-impact defect was established in the other reviewed paths. This is focused source/evidence review, not fresh browser acceptance for every page.

## Verification

`node --test --test-concurrency=1 tests/hiring.test.js tests/hr-workflow.test.js tests/research.test.js`: **38 passed, 0 failed, 0 skipped**. New regressions cover permission guidance, absent authoring controls, pending access recheck and evidence-navigation availability. The initial run failed one new test because its render imports were missing; imports were corrected and the complete focused selection passed.

Frontend lint and build passed, run once for this pass. Existing warnings: two Fast Refresh export warnings in SimulationContext/AppShell and the >500 kB main bundle. No backend, PostgreSQL or browser suite was run because the changes are frontend permission guidance and control availability. No dependency installation, test database credentials, containers or provider execution were needed. `git diff --check` passed. `AGENTS.md` content hash before/after: `b624574ff8d0b95ebe27812c8c0bbfc7f6c92014`.

Usage measurement: weekly used percentage was **78% before and 78% at the final pre-report check**, at the product's reported precision; short-window usage changed 73% → 74%. These are account-wide rounded readings, not an exact task token attribution. Stop after this pass.

## Deferred work and release boundaries

- No fresh browser/mobile/contrast sweep: existing acceptance is retained; no new visual-compliance claim.
- No new PostgreSQL acceptance or provisioning without separate approval. Existing verified cleanup remains historical evidence.
- Permanent deletion, migrations/RLS changes, invitation expiry/email delivery, live research and ATS expansion remain excluded.
- No production inspection/release or real Google/device/provider validation. Owner-reported production/recovery evidence remains explicitly attributed in the master tracker.

Manual real-user checks: a member without an HR responsibility should see clear guidance; Open Organizations should retain the workspace; an Owner/Admin should assign the role under Hiring responsibilities; returning and checking access should reveal only that role's authorized workflow. Test delayed Research trial loading, then opening the exact saved evidence. Also review Organizations, Agents and status/navigation on a phone and with keyboard/screen reader before release.

Next three actions:

1. Owner reviews this local commit and performs the role-assignment/recheck and delayed-evidence manual walkthrough.
2. Separately authorize manual publication/release, ensuring the usability sprint's read-only agent-eligibility backend endpoint is present before its dependent frontend; no schema migration is required by these fixes.
3. After authorized release, conduct real Google/profile/device and authorized multi-user acceptance; any live AI execution requires separate approval.

No push, deployment, production connection/change, database modification, live provider call or permanent deletion occurred. `AGENTS.md` remains untouched and untracked. Stop for owner review; do not initiate another autonomous task.
