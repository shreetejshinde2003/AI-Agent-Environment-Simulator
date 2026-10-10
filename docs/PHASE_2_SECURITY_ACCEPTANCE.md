# Phase 2 security acceptance

Date: 2026-10-10. Starting HEAD: `3ffabb3b56fa1119c1154690f7e0552973b1316a`, local `main`.

Status: COMPLETE for the authorized local Phase 2 investigation. **GO for local synthetic acceptance; NO-GO for release, real providers or production activation.** No production-deployed or production-verified claim. Required production/PostgreSQL evidence remains BLOCKED by missing authorization and evidence, not waived by this status.

## Scope and isolation

Reuse `OAUTH_RELIABILITY_AUDIT.md`, `OAUTH_PORTABILITY.md`, `RESEARCH_LIVE_DEMO_READINESS.md` and existing acceptance tests. Test settings override database/provider configuration in the test process; tests use disposable SQLite and mocked providers. An outer socket guard rejects IPv4/IPv6 connections, including accidental provider or PostgreSQL calls. No credentials/tokens belong in this report.

No branch, worktree, PR, push, deployment, real provider request, production connection, credential change, protected backup edit or application-data cleanup is authorized. Existing disposable test migrations are test-fixture setup, not application schema changes.

## Checkpoints

1. Baseline verified. Existing tests identified for OAuth/state/replay/stale identity, organization and HR boundaries/concurrency, research admission/attempt reservations and partial evidence, custom-agent revisions/retention and tenant uploads. Next: execute those focused selections and inspect user-controlled text/export gaps.
2. A: 62 passed; B: 98 passed; D: 100 passed. Focused frontend simulation/presentation checks: 40 passed. All had zero failures/skips. C first selection: 125 passed, one deadline-test failure; the same case failed again alone. The original 100 ms admission-to-deadline assumption prevented reaching transport. Correct the test timing, then recheck C. No application authorization bypass confirmed.
3. Supplemental existing upload/prompt-contract/HR-agent tests: 56 passed, 35 PostgreSQL tests skipped. No PostgreSQL URL provided; no provisioning attempted. New gap probes exercise concurrent approvals, archive/reactivation, eligibility after synthetic purge, malformed uploads, prompt source binding and CSV export formulas. Next: complete gap probes and final C selection, then document final release decision.
4. Final budget reacceptance: 66 passed, zero failures/skips. Final gap probes: 19 passed, zero failures/skips. Exact PKCE verifier/challenge binding verified over in-memory HTTP, including reverse callbacks. Local test correction/evidence commit: `2138d78` (`test: harden focused security acceptance and deadline probe`). No application security policy, retention policy, schema or runtime code changed. Next: finalize handoff and STOP.

## Confirmed defects and corrections

No application vulnerability was confirmed in the tested paths. This is bounded acceptance, not a proof that no vulnerabilities exist.

One confirmed acceptance-test correctness defect was corrected: `test_monotonic_deadline_interrupts_inflight_request` set a 100 ms budget before admission writes. It failed in the first 126-case selection and again alone with zero HTTP invocations, so it never tested in-flight cancellation. The corrected mock transport shortens the admitted deadline immediately before transport timeout scheduling. It now verifies exactly one transport invocation, `deadline_exhausted`, failed Tasks and no fabricated output. Existing admission/queue/expiry tests remain separate. All 66 budget cases pass afterward. No production deadline was changed.

New gap tests exercise existing mitigations rather than adding security behavior: tenant permission rechecks, immutable agent revisions, unsupported DELETE returning 405, serialized review decisions, upload size/encoding/format limits, inert source binding and CSV formula escaping. Every synthetic purge targets a disposable test-owned run only.

## A–E evidence

| Area | Accepted local evidence | Relevant coverage and limits |
| --- | --- | --- |
| A: authentication / sessions | 62 existing cases; one additional PKCE HTTP case in the gap group | Unique per-transaction cookies; state/cookie mismatch, expiry, consumed callback replay and nonce rejection; S256 and exact verifier binding; reverse callbacks/account switch, independent profiles, login recovery, session revocation and stale expected-identity mutation denial; browser origin/CSRF and WebSocket revocation. Simulated cookie jars and mocked Google claims/HTTP. Real Google signature/key rotation, native browser cookie policy and deployed forwarding not verified. |
| B: organization / HR | 98 existing cases; additional concurrent-approval case | Cross-tenant and direct API escalation denial; Owner/Admin/Member permissions; hashed one-use invitations, revocation and competing consumption; last-owner concurrent removal/demotion; independent Recruiter/Reviewer/Approver authority, revoked roles, actor spoofing, revision-bound state transitions and immutable review history. Two simultaneous final approvals yield one approved result and one 409, with one approval event. SQLite serialization only; PostgreSQL behavior remains a separate gate. |
| C: Research / AI | 126 distinct existing research/provider cases accepted; 66 budget cases rerun after correction | Server live/judge gates, exact B-direct digest/modes/repetitions, missing/lost budget state, retry-enabled hostile SDK fourth-attempt rejection, actual HTTP reservation before send, persistence failure, overlapping admissions, cancellation with queued work, exhausted reservations, expired budget, generated Report input, unaccounted request fields, launcher/PID/repository mismatch, hosted/multiple workers/replicas and second cooperating local process rejection. Failed/cancelled/partial runs keep authoritative failed status and partial/unknown usage; reports retain genuine partial evidence without declaring success. Real HTTPX/Groq SDK over MockTransport, no external requests. |
| D: custom agents / retention | 98 distinct cases in the agent/retention selection; two new lifecycle/retention gap cases | Cross-tenant reads/mutations denied; Owner/Admin manage, Member denial and removed-membership recheck; archived execution denied, reactivation preserves original revision; queued revision pinning and SQL immutable rows; eligibility permission check and 405 permanent deletion. Soft deletion retains run count; explicit synthetic purge makes retained runCount zero but eligible stays false, original revision remains. Zero retained runs is **not proof of historical non-use**. Current UI explicitly says retained runs; no historical tombstone is claimed. |
| E: uploads / exports / text | 56 supplemental existing cases (includes five repeated upload-ownership cases); 15 new upload/export/source gap cases | Traversal-style filenames normalized without filesystem writes; byte-stream limits, unsupported extensions, NUL/non-UTF8/nonfinite/deep JSON and malformed CSV rejected; tenant-scoped lookup/export. Formula-leading CSV text is apostrophe-escaped, including whitespace, while stored/JSON evidence is unchanged. Uploaded hostile-looking instructions remain JSON reference data and do not change deterministic routing. Existing HR output schemas reject an injected approval decision. Frontend React escapes HTML and refuses executable Markdown URLs. Model obedience to prompt instructions is not proven by mocks. |

The 19 new gap cases comprise PKCE (1), final approval concurrency (1), agent retention/lifecycle (2), and upload/export/source handling (15). The existing backend files and new gap suite exercise server enforcement; disabled frontend controls are not acceptance evidence by themselves.

## Exact results, failures and skips

Final distinct backend results: **454 passed, 0 failed, 35 skipped**. Focused frontend results: **40 passed, 0 failed, 0 skipped**. The durable case manifest is `docs/acceptance/phase2-security-results.json`; it records final outcomes and source runs without credentials, cookies or tokens.

Selections: A 62; B 98; C 126 (60 unchanged passing cases from the first selection plus the final 66-case budget rerun); D 98 distinct; supplemental E/PG selection 56 passes and 35 skips; final new gap group 19. Five upload-ownership cases occur in both D and E and count once in the 454 total. The first D command also repeated two upload API cases, yielding 100 passing invocations but only 98 distinct cases. Repeated passes are not inflated into new evidence.

All **35 skips** have the exact reason `TENANT_TEST_DATABASE_URL not set; live PostgreSQL enforcement unverified`: OAuth consumption 1, invitations/owners 12, HR reviews 13, custom agents 6, Research 3. No PostgreSQL test connection, provisioning or schema operation occurred. Checkpoint SQL/RLS suites were not rerun; their historical audits do not establish current acceptance.

Historical failures during this session, all resolved or superseded:

- Original research selection: 125 passes, 1 deadline-test failure. Isolated reproduction: 1 failure. Final corrected budget selection: 66 passes, zero failures/skips.
- Draft gap selection: 11 passes, 7 fixture/assertion failures (six missing required `StageExecution.output_key` values; one valid 2,000-level JSON accepted instead of the assumed rejection). Corrected fixtures use the existing stage schema and an input beyond decoder recursion capacity. A draft deadline probe was interrupted once after changing its deadline too late to reschedule the active timeout; it provides no acceptance evidence. The corrected gap-plus-deadline selection passed all 19 cases.
- First additional PKCE probe: 18 passes, 1 incorrect expected-redirect assertion (303 vs existing 302). Corrected final gap selection: 19 passes, zero failures/skips.

Two warning categories recur in backend selections: Starlette/AnyIO `BlockingPortal` deprecation and LangGraph's pending `allowed_objects` default change. No full backend/frontend suite was repeated; no frontend implementation changed, so lint/build were not rerun. `git diff --check` passed. No new native browser acceptance is claimed: TestClient cookie sessions and frontend state/SSR tests are simulated browser evidence.

## Reproduction / safe resume

From the repository root, use the existing environment and the committed socket-blocking runner. It selects disposable default SQLite, synthetic provider settings, disabled gates and removes opt-in PostgreSQL URLs **inside the test process only**. Individual fixtures still mock providers and temporarily enable only their synthetic test path. It neither edits `.env` nor contacts providers:

```text
.venv/bin/python backend/tests/run_phase2_security_acceptance.py auth -q -ra
.venv/bin/python backend/tests/run_phase2_security_acceptance.py organization-hr -q -ra
.venv/bin/python backend/tests/run_phase2_security_acceptance.py research -q -ra
.venv/bin/python backend/tests/run_phase2_security_acceptance.py agents-retention -q -ra
.venv/bin/python backend/tests/run_phase2_security_acceptance.py text-postgres-gates -q -ra
.venv/bin/python backend/tests/run_phase2_security_acceptance.py gaps -q -ra
cd frontend
node --test --test-concurrency=1 tests/session-sync.test.js tests/output-consolidation.test.js tests/agent-builder.test.js tests/research.test.js
```

These commands are for changed-boundary reacceptance, not instructions to repeat completed work next session. For the corrected deadline alone, use group `budget` and `-k monotonic_deadline_interrupts_inflight_request`. The runner deliberately cannot authorize PostgreSQL or live calls.

## Outstanding release blockers / human decisions

1. Restricted local PostgreSQL/RLS acceptance is unverified. Before provisioning any role/database/schema, request explicit authorization for least-privilege localhost-only disposable setup and teardown. Reaccept OAuth consumption, invitation/owner races, HR approvals/source immutability, custom-agent retention and Research isolation with zero skips. Production is a separate authorization.
2. Existing `OAUTH_RELIABILITY_AUDIT.md` records an unresolved deployed callback-cookie omission and coordinated release order; `RELEASE_READINESS.md` records the direct Railway WebSocket cookie/session topology gate. Neither was inspected against production here. An authorized operator must verify deployed versions, cookie forwarding, fresh login/logout/relogin, shared-browser switching and stale mutations through Vercel, plus authenticated WebSocket expiry/revocation.
3. `RESEARCH_LIVE_DEMO_READINESS.md` remains an estimated-budget policy, not a hard token/billing guarantee. Real provider execution requires separate explicit approval of that uncertainty and the pinned dedicated single-process protocol. No enabling/configuration/credential work is permitted by Phase 2 completion.
4. Current run purge deletes execution evidence; retained-run counts cannot attest historical non-use. Referenced HR AI evidence retention remains an explicit policy decision in the existing OAuth/release audit. A requirement for tombstones, non-purgeable review-associated outputs or lifetime usage proof is **BLOCKED pending retention-policy/schema approval**; no such change was attempted.

## Next phase and stop instruction

The next roadmap phase is **Phase 3**. Its title/directive is absent from the supplied eight-phase roadmap, so do not invent its scope. Human instructions: review this report and the local test commit, supply the exact Phase 3 directive and expected local-main HEAD, and state any new approvals explicitly. Reconcile the prior Phase 1 acceptance record in the tracker without restarting its work. Release blockers above remain open until separately authorized and evidenced.

At handoff, two local commits at most: test correction/evidence `2138d78`, then the documentation commit containing this report/tracker/manifest. The documentation commit cannot embed its own hash; retrieve it with `git rev-parse HEAD`. Final working-tree acceptance requires only `?? AGENTS.md`, whose SHA-256 remains `a5f46def185ce9e844d9d468912f3fbee4dbf2d8f14f08c91c02553352e87efd`. STOP: do not start Phase 3, enable Groq, publish or deploy.
