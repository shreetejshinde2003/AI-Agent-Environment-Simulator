# Product usability sprint — local acceptance

Starting commit: `f8c75be881a32dbdbe0000f2de89818ac26d226d`, local `main`, initially only untracked `AGENTS.md`. All work stays local on main. No branch/worktree/PR, push, production deployment/configuration/SQL or live Google/Groq call. Operational schema remains 14; existing SQLite application files were not selected for browser fixtures.

## User-visible changes

- **Organizations:** first-use create/join actions, direct named workspace opening, useful saved/uncertain/error feedback, ordinary-language Owner/Admin/Member guide, invitation copy/hide, actual pending/consumed/revoked history, confirmation before replacement/revocation/access changes, and working member refresh after a join. Last-owner/server permissions remain unchanged. Unique panel keys prevent duplicate panels and old code redisplay on workspace switches. Invitation codes have no timed expiry in the current implementation; the UI explicitly states valid until use, revocation or replacement rather than inventing expiry/email delivery.
- **Status:** Ready/Updating/Connection problem/Sign in again presentations; last successful refresh, manual refresh and secondary connection details. Existing REST refresh remains every five seconds. Application WebSockets require an explicit frontend opt-in and default off; an endpoint URL alone does not enable them. No socket endpoint/authentication/proxy change.
- **Research:** separate welcome/sample/new/saved experiences. The 42-trial example is a byte-identical copy of the legitimate historical phase-10 fixture report, pinned by manifest SHA-256 and validated as fixture evidence. It is read-only and not imported into workspace history. Case inputs, real saved outputs/stages/routes/reference checks and limitations are inspectable. New experiments keep the server gate and use a trial/provider review dialog before existing admission. Saved results reload and export through existing APIs; no superiority/cost/training claim is added.
- **HR Hiring:** five-step guide projects the existing state machine; saved requirement/JD actions, optional AI proposal/knowledge review, real submission, recommendation then final authorized decision. Required inputs have examples; optional fields, version/actor metadata and source/history relationships are disclosures. Saved notices explain where work is found and that approval is not automatic. Owner/Admin still has no implicit HR grant. Missing AI evidence no longer promises that purged output is retained.
- **Custom agents:** clearer authoring/run/result instructions, archive confirmation, explicit reactivation, and a manager-only server dependency report. Counts include soft-deleted runs; revisions/config hashes/authorization remain protected. Built-ins remain protected. No deletion endpoint was introduced.
- **Cross-page:** navigation returns focus/scroll to content; native dialogs preserve keyboard containment/return focus; mobile layouts and truthful empty/error states remain usable. [PROJECT_MASTER_STATUS.md](PROJECT_MASTER_STATUS.md) is the current tracker; old phase reports are historical evidence.

## Deliberate deletion deferral

Permanent deletion of saved custom agents is **not implemented**. Even an unused saved definition has an immutable creation revision with a restrictive FK, SQLite UPDATE/DELETE guards and PostgreSQL insert-only revision policy. Current retained-run count also cannot prove never-used status after legitimate run purge. A safe exception needs an approved retention migration, authoritative usage marker, conservative legacy handling, transactional dependency checks and exclusion against run admission. No guard was weakened and no schema/data cleanup was performed. Archive/reactivate are fully available. The disabled permanent-delete control explains this actual limitation rather than pretend to execute deletion.

## Exact validation

| Selection | Final result | Evidence |
|---|---|---|
| Consolidated related backend/security/API/storage regression | **440 passed, 6 skipped, 0 failed**; 2 dependency warnings | [backend.txt](acceptance/usability-sprint/backend.txt) |
| Additional strengthened manager/member eligibility assertions | **3 passed, 0 failed/skipped**; cases already included in the above selection, not added to 440 | [agent-manager-checks.txt](acceptance/usability-sprint/agent-manager-checks.txt) |
| Full frontend suite | **230 passed, 0 failed/skipped** | [frontend.txt](acceptance/usability-sprint/frontend.txt) |
| Local Chrome browser journeys | **41 passed** | [browser-results.json](acceptance/usability-sprint/browser-results.json) |
| Frontend lint and build | Pass | [lint.txt](acceptance/usability-sprint/lint.txt), [build.txt](acceptance/usability-sprint/build.txt) |
| Python/JS syntax and Git whitespace | Pass | Final local checks |

Six skips are the opt-in local PostgreSQL custom-agent cases, including the new eligibility test, because `TENANT_TEST_DATABASE_URL` was not supplied. No temporary PG credentials/schema were provisioned in this sprint. The preceding 43-case restricted PG acceptance belongs to the earlier baseline; it does not establish fresh SQL enforcement for this added read query. Existing schema/RLS definitions were unchanged and their contract tests passed. This is the remaining database acceptance requirement before claiming current PostgreSQL acceptance.

Warnings: existing Starlette/AnyIO deprecation and LangGraph serializer pending deprecation; two existing Fast Refresh export warnings; >500kB main-bundle warning. No failing check remains in final runs. Early browser attempts exposed a fixture CORS issue and duplicate component keys; both were corrected. Membership refresh and accessible control naming were completed through real browser checks. Harness selector corrections were not treated as application failures. No broad execution-engine regression was repeated because execution code was unchanged.

## Browser evidence and boundaries

Real local React/FastAPI/SQLite requests used a disposable fixture at ports 5181/8031. Google was not invoked. Research/custom-agent SDK and HR provider responses were deterministic mocks installed before admission. The sample opened with **zero provider calls**. The exercised new fixture experiment and agent run recorded 10 mocked SDK calls, plus one mocked HR proposal; these are not real Groq usage/cost. There were **zero `/ws/live` attempts**. Separate Chrome contexts represented different authenticated humans; the shared-profile switch check reloaded server authority.

Acceptance covered create/join/consumed invitation and masked history; copy/hide; workspace switching; replacement/revocation; confirmation keyboard Tab/Escape/focus return; member role changes; last owner; sample source/answer; disabled admission; reviewed 3-trial fixture experiment and persisted reload; requirement/JD/source saving; optional AI proposal; Recruiter submission without decisions; separate Reviewer recommendation and Approver final approval; IAM-only denial; agent dependency/archive/reactivation/output; real HTTP polling interruption/recovery; and mobile Organizations/Research/HR/Agents.

Screenshots show synthetic local identities and records; invitation secrets are hidden:

- [Organizations desktop](acceptance/usability-sprint/organizations-desktop.png), [mobile](acceptance/usability-sprint/organizations-mobile.png).
- [Historical research sample](acceptance/usability-sprint/research-sample-desktop.png), [mobile](acceptance/usability-sprint/research-mobile.png).
- [HR approval](acceptance/usability-sprint/hr-approved-desktop.png), [mobile guide](acceptance/usability-sprint/hr-mobile.png).
- [Agents desktop](acceptance/usability-sprint/agents-desktop.png), [mobile](acceptance/usability-sprint/agents-mobile.png).

Mobile viewport checks are not physical-device/assistive-technology acceptance. The original fixture JSON remains unchanged under docs; the served copy is labelled and separately loaded rather than new live execution data. Schema-14 backup/release/real-provider acceptance remains outside this sprint.

## Safe reproduction and manual acceptance

Use only the local disposable fixture; never expose/import its session or control routes in production. From repository root:

```sh
.venv/bin/python backend/tests/usability_sprint_browser_fixture.py
```

From frontend/ in another terminal:

```sh
VITE_API_BASE_URL=http://127.0.0.1:8031 VITE_LIVE_UPDATES_ENABLED=false npm run dev -- --host 127.0.0.1 --port 5181 --strictPort
```

With an available Playwright module and installed Chrome, run from repository root (set `FM_PLAYWRIGHT_MODULE` to that package directory if not normally resolvable):

```sh
node backend/scripts/usability_browser_acceptance.cjs
node backend/scripts/usability_mobile_acceptance.cjs
node backend/scripts/agent_dependency_browser_acceptance.cjs
```

The main runner assumes fresh fixture data; restart only your owned fixture before rerunning it. Stop both owned servers after acceptance; backend shutdown removes its disposable SQLite directory. No existing application/production data is deleted. Normal manual walkthrough and next acceptance gates are in the master tracker. Local commits are for owner review; publishing/deploying remains manual and separately authorized.
