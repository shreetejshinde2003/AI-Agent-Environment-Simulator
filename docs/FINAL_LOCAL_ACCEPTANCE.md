# Final local acceptance — 2026-10-10

Baseline: local `main`, `7b643d2c5dc939a37955974f41b9da56f4c97cbc`. This is a focused continuation of the completed usability sprint. No production connection, push, deployment, cloud setting change, live provider call, application migration or permanent agent deletion occurred. `AGENTS.md` remains untouched and untracked.

## Concrete corrections

- **Custom Agents:** release the execution lock in `finally`, so another run, save or archive is possible on the same mounted page. History/status reads share the lock rather than releasing a concurrent mutation's lock. Textarea accessible names remain stable after entering text.
- **Organizations:** unknown invitation history cannot be treated as an empty list. Creation/replacement/revocation waits for a successful read; failed mutations clear displayed secrets and require a refresh before another change. Replacement confirmation and server permissions remain intact.
- **HR Hiring:** choose the newest saved JD by creation timestamp rather than array position (API order and local prepend order differ). Suggestions open only matching saved evidence; absent optional suggestions are explained and disabled. Recruiter feedback leads back to editing a revision rather than a terminal review request. Existing HR state machine and IAM/HR separation remain authoritative.
- **Research Lab:** accept the real fetched same-workspace Task before selecting it in Simulation, preventing fallback to an unrelated cached run when collection polling lags. Trial selection has a stable accessible name. Sample evidence and disabled-live gates remain unchanged.
- **Master status:** adds the owner's independently reported production OAuth/recovery results with explicit attribution and structural/sample-data limitations; does not claim fresh production tests.

Code: `frontend/src/components/dashboard/AgentBuilder.jsx`, `components/organizations/OrganizationInvites.jsx`, `components/hiring/HRJourney.jsx`, `utils/hrWorkflow.js`, `pages/ResearchLab.jsx`. Regression infrastructure: `frontend/tests/hr-workflow.test.js`, `tests/usability-sprint.test.js`, `backend/scripts/usability_browser_acceptance.cjs`.

## Fresh restricted PostgreSQL acceptance

Explicit approval was obtained before any local SQL, credentials or objects were created. Existing container: `fm-tenant-postgres`, `postgres:16-alpine`, sole binding `127.0.0.1:55432`. A uniquely named new database was admin-owned; PUBLIC database rights were revoked only on that new database. The temporary login received CONNECT/CREATE there, enabling isolated test-owned schemas, with NOSUPERUSER/NOBYPASSRLS/NOINHERIT/NOCREATEDB/NOCREATEROLE/NOREPLICATION, zero memberships, eight connections and one-hour expiry. Private credential directory/file permissions were 0700/0600. No `.env` or process environment configuration was changed.

The existing `pg_repo` infrastructure read a test-only URL injected into its module-local environment adapter. A connection guard rejected connections outside the exact disposable identity/database/loopback address; HTTP/provider transport was blocked. Existing test mocks supplied execution responses.

`backend/tests/test_agent_builder_postgres.py`: **6 passed, 0 failed, 0 skipped**:

1. Definitions/revisions FORCE RLS and tenant denial.
2. Member/manager/inactive-member enforcement at repository and RLS levels.
3. Additive version-10 fixture migration to current schema **14**, repeated initialization and preserved existing evidence.
4. Mocked custom execution, StageExecution persistence and disposable recycle evidence.
5. Unicode name casefold behavior.
6. Deletion eligibility, immutable revision guards and tenant boundary.

The migration manipulation and purge assertions were exclusively inside disposable test schemas; existing databases were never migrated or purged. This six-case run is not a repeat of the earlier schema-13→14 OAuth-ledger check, nor PostgreSQL 18 or production acceptance.

Cleanup verified: NOLOGIN and password NULL before removal; temporary sessions terminated; disposable database and login dropped; private credentials deleted; zero remaining temporary database/role/sessions. The original database schema fingerprint and role/database/membership catalog fingerprint match before/after. Password hashes were not collected. [Machine-readable cleanup evidence](acceptance/final-local-pg-cleanup.json).

| Existing checkpoint schema | Checkpoints | Blobs | Writes | Migration rows | Before/after |
|---|---:|---:|---:|---:|---|
| `fm_tenant_test.public` | 13 | 18 | 44 | 10 | Identical |
| `fm_tenant_test.langgraph_checkpoints` | 0 | 0 | 0 | 10 | Identical |

## Regression results

- Full frontend suite: **232 passed, 0 failed, 0 skipped** (`npm test`).
- Focused backend `test_agent_builder.py`: **52 passed, 0 failed**. The initial combined run reported six unconfigured-PG skips, all six subsequently passed in the approved restricted run above; no PostgreSQL case remains unverified in this selection.
- Frontend lint/build pass; two existing Fast Refresh warnings and the existing >500 kB bundle warning. Backend warnings: Starlette/AnyIO and LangGraph deprecations; restricted in-process pytest additionally reports preimported Langsmith/AnyIO assertion-rewrite warnings.
- Real local Chrome acceptance: **42 passed, 0 failed, 0 skipped**, using the existing disposable SQLite fixture and mocked SDK/HR responses (**10 SDK calls, 1 HR call; zero live calls**). Default application WebSocket attempts: **0**. Coverage includes invitation read-failure recovery, used-code rejection, exact research evidence navigation despite an empty delayed collection response, saved experiments, Recruiter→Reviewer→Approver, IAM-only denial, repeat agent runs followed by editing/saving, polling failure/recovery, mobile Organizations/sample layouts and shared-profile session reconciliation. [Per-check results](acceptance/final-local-browser-results.json).

Intermediate exploratory browser runs exposed changing accessible names on controlled textarea/select labels; stable names now pass repeated use. The harness also needed to await asynchronous invitation recovery and inspect raw recorded output rather than rendered formatting. One new unit assertion was corrected for the existing Button's inner span. These intermediate failures are not silently counted as successful acceptance; the final complete reruns above exited successfully. No fresh keyboard-focus sweep or physical-device/real-Google test was performed; the previous sprint's keyboard coverage remains historical evidence.

## Remaining boundaries and manual handoff

No new retention/deletion feature or migration is included. Permanent custom-agent removal remains disabled under immutable-revision policy. Invitations have no timed expiry or email delivery. Research live execution stays server-gated; historical sample evidence is fixture-only. Full ATS/candidate/resume handling is outside this JD workflow. Real Google/multi-device acceptance and post-release real-user workflows remain separate gates. Reported PostgreSQL 18 restore limitations are preserved in the master status, including the nonfatal existing `postgres` role conflict and absence of exact all-table snapshot count parity.

Manual acceptance after separately authorized publication:

1. Organizations: create/join with two identities, hide/leave/return, used/revoked code errors, confirmed replacement, last-Owner protection. Interrupt invitation-history loading and verify actions remain disabled until recovery.
2. Research: explore labelled 42-trial sample; inspect inputs/output/provenance. Confirm live-disabled action. In the local approved fixture only, save/reload an experiment and open the exact trial evidence.
3. HR: requirement → draft → optional suggestions/sources → submission → Reviewer recommendation → Approver decision. Request changes, edit/resubmit, retain prior history. IAM-only users must have no HR authority.
4. Agents: save, run twice on the same page, edit/save afterwards, archive/reactivate, inspect retained history. Verify permanent deletion remains disabled and built-ins protected.
5. Check default polling/no socket, interruption/recovery, shared-profile session reconciliation, mobile navigation and keyboard dialog focus.

Schema/deployment compatibility: frontend-only runtime corrections use existing schema-14 APIs. No backend release or SQL migration is required by this continuation. The prior usability sprint's read-only eligibility endpoint must be present before publishing its dependent frontend. Keep any deployment holds until the owner explicitly authorizes manual release. **Stop before push/deployment.**
