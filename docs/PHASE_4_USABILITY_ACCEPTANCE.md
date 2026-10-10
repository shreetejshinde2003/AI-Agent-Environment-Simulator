# Phase 4: final user workflow and accessibility acceptance

Date: 2026-10-10. Actual starting HEAD: `59d7d233c873565b7a0b26b12657bd57127a2a04`, existing local `main`, only `?? AGENTS.md` at entry. Phase 1–3 work remains closed. No push, deployment, production access, live Google/Groq request, Research gate activation, PostgreSQL provisioning, schema migration, authorization-policy change or permanent agent deletion is part of this phase.

Status: **COMPLETE for bounded local workflow/accessibility acceptance; production and real-user/device acceptance remain separate gates.** Confirmed application failures were corrected; no unresolved failure remains in the exercised local workflow checklist.

## Isolation and scope

Browser acceptance uses local Chrome, Vite on `127.0.0.1:5181`, and the dedicated test fixture on `127.0.0.1:8031`. The fixture reuses existing authoritative HR/organization APIs and storage in disposable temporary SQLite. Synthetic accounts have distinct Recruiter, Reviewer, Approver, combined, IAM Admin and Member responsibilities. Sessions are test-only opaque local cookies, never Google login sessions or production identities.

HR AI and custom-agent SDK completions are deterministic mocks. External browser requests are blocked, and the backend fixture rejects external socket connections. Existing application credentials and environment files are not changed. All Research live/judge/demo gates stay false, and the fixture has no gate-enabling endpoint. Existing historical synthetic trial payloads are imported into the isolated fixture database for actual persisted-result read APIs; no new research admission/execution occurs. This is synthetic machinery evidence, not a live model result or proof of real Google authentication.

Test-fixture initialization creates only its disposable SQLite tables. It does not migrate an existing application database or provision PostgreSQL objects. Original historical report/sample bytes and records are unchanged; frontend checksum tests reverify the historical sample.

## Confirmed fixes

1. **Research read failure had no recovery action and falsely claimed empty history.** A mocked 503 on the initial benchmark read left no retry button; switching to saved experiments displayed “No experiments yet” despite 42 persisted fixture trials. Research now offers “Reload research workspace” and displays an empty history/count only after a successful scoped load. Screenshot review caught the related unknown-count `(0)` label, which is now suppressed until confirmation. Retry retains the disabled execution gate. A browser regression recovers using keyboard Enter and reloads the real saved list.
2. **Enabled primary action labels and accent headings had insufficient normal-text contrast.** White on the prior indigo button background measured 4.467:1; the organization eyebrow measured 4.321:1 and sidebar “Workspace totals” measured 3.887:1. Separate action/text tokens now give white action text 4.933:1 and accent text 8.709:1 on the sidebar surface / 9.681:1 on the app surface. Only affected action/heading styles changed. A token contrast regression and a rendered browser probe verify these combinations. Disabled controls and decorative aria-hidden avatars are outside these text checks; this is not whole-application WCAG certification.
3. **Benchmark details were nested inside checkbox labels.** The accessible case name included “Directive, source and criteria” and could grow with expanded technical content. Each checkbox now has a stable case-title label; rationale and expandable evidence are separate siblings. Browser regression opens/closes the details using Space without changing the selected case or accessible name.

No HR authorization, organization policy, agent retention/revision behavior or server execution code changed. A suspected HR loading race was withdrawn: a saved textarea's text affected Playwright's exact `getByLabel` selector, while its actual accessible textbox name was correctly “Summary” and the record did load. The unneeded provisional HR navigation lock was removed. Reopened saved-draft edits use `getByRole('textbox', {name:'Summary', exact:true})` in acceptance.

## Exercised workflows

| Workstream | Local evidence exercised | Boundary / outcome |
| --- | --- | --- |
| Organizations | Create; copy/hide one-use invitation; switch Personal/organization workspaces; join; invalid/used/revoked codes; failed invite-history read and refresh; role explanation; Member controls/API denial; Owner role change; last-Owner protection; cancel/confirm member removal | Real synthetic memberships and invitation history. Removed membership returns the existing opaque 404, not an authorization bypass. |
| HR access | Owner without HR responsibility denied by the records API and given actionable guidance; assign Recruiter through real member controls; recheck access in the already-mounted HR screen; IAM Admin without HR role denied | Organization authority stays separate from HR authority. Rechecking acquires newly assigned responsibility through existing server APIs. |
| Guided HR hiring | Save requirement; optional mocked AI proposal; manually save source-bound JD; Recruiter submission with no decision controls; Reviewer recommendation; Approver approval and notes; workspace refresh; reopen/edit JD; fresh revision-2 submission while revision-1 approval/history remain visible | Existing immutable sources and human decision state machine retained. AI neither adopts a draft nor approves anything. |
| Research Lab | Historical 42-trial sample; methodology/limitations, source checks and saved answer; configure case/repetition counts without execution; server-disabled explanation; persisted 42-trial history and exact Task evidence despite delayed task-list visibility; retry after 503; keyboard-focusable comparison table | Sample/static and server-persisted synthetic results are labelled fixture evidence. No gate enabling, provider request or new experiment execution. |
| Custom agents | Create; dependency/removal explanation; archive confirmation; disabled archived execution; reactivate; two mocked executions in the same mounted screen; edit to revision 4; inspect earlier revisions; disabled permanent deletion | Authoritative definition, revision and run APIs. Original revisions remain inspectable; no DELETE endpoint introduced or invoked. |
| Overall UX | Named navigation and fields; dialog Tab containment, Escape and return focus; keyboard retry/table/details; mobile overflow checks; connection failure and polling recovery; shared-profile synthetic identity change clears prior HR authority/workspace | Browser automation with local cookies and mocks. Unexpected main-page errors/external requests are checked; default polling makes zero application WebSocket attempts. |

Final full browser result: **60 passed, 0 failed, 0 skipped**. An additional focused mode-selection check passed with zero mock/provider invocations; a narrow repeat of Research recovery verified the final unknown-count correction. These narrow runs are recorded separately, not added as two new distinct full-checklist successes. The full checklist recorded two mocked custom-agent SDK completions and one mocked HR proposal, zero live calls, zero application WebSocket attempts and all Research gates false. Screenshots and machine-readable checklists live under `docs/acceptance/phase4-usability/`; screenshots were visually reviewed and mobile captures were scrolled to the actual forms/sample. Read-only screenshot recapture left mock counts unchanged.

## Focused tests and evidence

- Frontend selection: **74 distinct passed, 0 failed, 0 skipped** across organizations, members/HR-role management, hiring workflow/reviews/assistance, Research, agents and usability. After the temporary HR diagnosis was withdrawn, the affected hiring/Research/usability selection was rerun: **40 passed, 0 failed, 0 skipped**. Following the final count-label correction, Research alone passed **12/0/0**. Repeat passes do not add to the 74 distinct count. One new mathematical contrast regression is included.
- Backend: **12 passed, 0 failed, 0 skipped** in `test_hr_workflow_integration.py`, using the existing outer socket-blocking runner, synthetic SQLite and mocked providers. No historical security/PostgreSQL suite repeated.
- `npm run lint` and `npm run build`: passed. Existing lint warnings concern non-component exports in AppShell/SimulationContext; build retains the >500 kB bundle warning. Backend retains Starlette/AnyIO BlockingPortal and LangGraph allowed_objects dependency warnings.
- Browser regressions cover Research failed-load recovery, stable benchmark labels, plus successful/denied user paths and retained evidence. Recorded contrast checks are additional to the workflow checklist.
- `git diff --check`: passed before committing. No native browser/device, screen-reader or production acceptance is inferred from unit/SSR tests.

Some exploratory browser commands stopped while building this checklist: the first fixture had a local CORS-list mismatch; an initial saved-list selector ran before options loaded; a role-checkbox assertion expected immediate state before the real write completed; reopened textarea label selectors included saved text; repeated revision-status text needed disambiguation; removed-member denial intentionally used 404; editing an export during a diagnostic run triggered Vite Fast Refresh. These are harness/diagnostic interruptions, not inflated successes or confirmed application vulnerabilities. Final evidence replaces interrupted checklist output; the Research read/contrast/label reproductions above remain the confirmed defects.

Reproduce from repository root, with installed Chrome and an available Playwright package, using only isolated test data:

```sh
.venv/bin/python backend/tests/phase4_usability_browser_fixture.py
```

In another Terminal:

```sh
cd frontend
VITE_API_BASE_URL=http://127.0.0.1:8031 VITE_LIVE_UPDATES_ENABLED=false npm run dev -- --host 127.0.0.1 --port 5181 --strictPort
```

Then, from repository root (set `FM_PLAYWRIGHT_MODULE` to the installed package directory if needed):

```sh
node backend/scripts/phase4_usability_acceptance.cjs /private/tmp/fm-phase4-review
node backend/scripts/phase4_usability_acceptance.cjs /private/tmp/fm-phase4-review --recovery-only
node backend/scripts/phase4_usability_acceptance.cjs /private/tmp/fm-phase4-review --configuration-only
cd frontend
node --test --test-concurrency=1 tests/hr-workflow.test.js tests/research.test.js tests/usability-sprint.test.js
```

Start with a fresh fixture per full workflow run; the configuration-only check requires a fresh fixture so its zero-invocation assertion is meaningful. The recovery-only check may reuse saved fixture evidence. Do not edit application files while the browser checklist runs. Do not use the older usability fixture or its Research-enabling route for this phase. Stop both dedicated processes afterward; the backend `finally` disposes the fixture engine and removes its temporary directory. Ports must not be occupied by another application; do not terminate unrelated processes.

## Remaining usability problems and manual involvement

No unverified usability issue is silently marked fixed. The large application bundle remains a performance concern for slow devices; this phase did not introduce a broad code-splitting redesign. Expanded mobile navigation occupies much of the first viewport, so actual forms require scrolling; usable scrolling and fit were checked, while a novice's navigation preference needs real-device review. Technical provenance/JSON views remain deliberately secondary; whether their explanations suffice for first-time users needs an actual novice-user walkthrough. Two trials/sample metrics do not establish quality, significance, provider latency or cost.

Chrome emulation at desktop 1440×1000 and mobile 390×844 / 320×844 verifies layout and selected keyboard interactions, not real touch devices, Safari/Firefox, zoom/font scaling across every page or a complete screen-reader journey. The normal-text contrast fixes cover measured components, not every state/graph/chart. No automated whole-app accessibility engine or WCAG conformance certification is claimed. An owner/user should complete the workflows on an actual phone and with their preferred assistive technology; navigation, validation/error announcements, modal focus and dense evidence tables need manual review.

Real authenticated Google login, provider output behavior, external provider failure/cancellation and deployed proxy/cookie/session/WebSocket behavior remain separate authorized acceptance gates. Research execution remains disabled, so the new-experiment configuration/denial and persisted-results paths are accepted, while actually launching a provider experiment is intentionally unexecuted. No live run is fabricated to fill this gap.

## Phase 5 prerequisites and stop

Phase 5 remains **NOT STARTED**. Required before any deployment work:

1. Owner reviews this Phase 4 report and supplies the exact Phase 5 scope and explicit production/deployment authorization. Local passes do not authorize push/deploy or production data/credential access.
2. Resolve the existing deployed OAuth callback-cookie/release-order gate through separately authorized verification of frontend/backend versions, same-origin API forwarding, login/logout/relogin, shared-browser switching and stale mutation denial. Google configuration/secrets must use the approved secret workflow, never source or test-session cookies.
3. Keep direct Railway WebSocket cookie/session topology as a gate. Default REST polling is accepted locally; live WebSockets require explicit deployed authentication/expiry/revocation evidence before enabling.
4. Verify production runtime roles, tenant/RLS enforcement and schema/version compatibility under separately authorized read-only/operational scope. Phase 3 restricted PostgreSQL evidence is local-only. Any production backup/migration/retention-policy operation needs its own authorization; existing backup files remain untouched.
5. Resolve the existing retention-policy decision for review-associated AI evidence, without enabling permanent agent deletion. Preserve original revisions/history; no policy/schema change was authorized here.
6. If a live Research demonstration is desired, obtain separate approval for the Phase 3 isolated runbook, synthetic session/key handling and estimated token/billing uncertainty. Production deployment or Phase 4 completion does not imply that approval.

Implementation commit: `412061fc05a1554f24579a73dadf611bec8040f0` (`fix: recover Research reads and improve accessible labels`), containing six frontend fix/test files plus the isolated fixture and browser checklist. The second/final local checkpoint contains this report, tracker, sanitized evidence and the focused configuration-check option. The ending HEAD is that checkpoint commit and is retrieved with `git rev-parse HEAD`; a commit cannot embed its own hash.

Cleanup verification is saved in `acceptance/phase4-usability/cleanup.json`: dedicated acceptance processes/listeners stopped; disposable SQLite directory (including synthetic sessions/accounts) removed; normal Research live/judge/demo and graph gates false; original historical report unchanged. No credential/environment file, production record or backup was changed. Final working tree must contain only `?? AGENTS.md`, whose SHA-256 stays `a5f46def185ce9e844d9d468912f3fbee4dbf2d8f14f08c91c02553352e87efd`.

**STOP after Phase 4 for owner review. No push, deployment, live execution or Phase 5 work.**
