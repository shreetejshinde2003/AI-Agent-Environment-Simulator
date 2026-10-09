# OAuth reliability audit — 2026-10-09

## Outcome and scope

**The exact production cause of `invalid_oauth_state / missing_transaction_cookie` remains unproven.** Current code reproduces that safe failure when the callback's matching cookie is absent, including when returned state maps to a different cookie name. The local HTTPS browser accepted the unique Secure/HttpOnly/Lax cookie and completed cross-site mocked Google callbacks without cookie rejection. Three repeated starts and concurrent pending tabs did not reproduce spontaneous cookie loss.

Confirmed defects corrected locally: raw JSON after browser callback failure, raw JSON on browser login misconfiguration, stale account/workspace state in other tabs, retained presented old session after account switch, and repeated React effect setup losing callback failure feedback when an older session remained valid. No transaction format, schema, tenant/IAM/HR policy, RLS or production configuration was changed.

Starting branch/HEAD: `main`, `cc96b6d6f2b409a275aa50dc80d6db3784902abc`; status only `?? AGENTS.md`; cached local/origin comparison `0 0`. No fetch was performed, so this is not freshly refreshed GitHub evidence. All work stays on local main. No push, branch, PR, deploy, Google Console/environment change, production credential/SQL access or real Google/Groq call.

Prior evidence inspected: `OAUTH_PORTABILITY.md`, `POST_DEPLOYMENT_PRODUCT_CORRECTIONS.md`, Phase 2/5–10 architecture/acceptance reports, release readiness and current code. Earlier successful PostgreSQL runs are historical local evidence; they did not prove the failed production browser's cookie delivery or current deployed backend/frontend identity.

## Lifecycle traced from code

```mermaid
sequenceDiagram
  participant B as Browser profile (shared tabs)
  participant V as Vercel origin
  participant R as Railway API
  participant D as Application database
  participant G as Google
  B->>V: Top-level GET /api/v1/auth/google/login
  V->>R: Same-origin rewrite
  R->>D: Save state/cookie digests + expiry
  R-->>V: 302 Google + unique transaction Set-Cookie
  V-->>B: Host-only Secure/HttpOnly/Lax callback-path cookie
  B->>G: State, nonce, S256 PKCE challenge, exact redirect
  G-->>B: Top-level GET Vercel callback (code + state)
  B->>V: Matching transaction cookie
  V->>R: Forward callback and cookie
  R->>D: Conditional one-time DELETE matching unexpired digests
  R->>G: Exchange code with verifier + same redirect URI
  R->>R: Verify token signature/audience/issuer/expiry + nonce + verified identity
  R->>D: Identity / workspace / new session digest; revoke presented old session
  R-->>B: Shared app_session + redirect /?auth=success
  B->>V: /auth/me; server-authorized workspace discovery
  V->>R: Credentialed REST
  R->>D: Session + workspace/IAM checks
  R-->>B: Public profile and accessible workspace bootstrap
```

References:

- `frontend/src/pages/Login.jsx`, `services/authClient.js`, `hooks/useAuth.js`, `App.jsx`: login navigation, bootstrap/recovery, keyed account provider.
- `frontend/src/services/apiConfig.js`: production relative REST; development configurable API origin. `frontend/vercel.json`: `/api/v1/:path*` rewrite before SPA fallback; no-store auth headers.
- `backend/app/api/routes/auth.py:_require_google_configuration/google_login/_complete_google_callback/_authenticated_record/me/logout`: complete authority path. Provider exchange timeout is 15s; token verification is moved to a worker thread.
- `backend/app/security/session.py`: 32-byte random state/nonce/session, S256 PKCE pair, hashed transaction name, TTL/session duration and auth-query access-log redaction.
- `backend/app/storage/database.py:save_oauth_transaction/consume_oauth_transaction/save_auth_session/revoke_auth_session`: persistence/one-time DELETE ledger and hashed opaque sessions; schema-14 table defined in `storage/models.py`.
- `backend/app/security/browser_origin.py`: mutation Origin/Referer validation independent of CORS plus all auth-response no-store headers. No proxy Host/X-Forwarded-* value selects trusted redirect or cookie security.
- `backend/app/api/routes/workspaces.py:require_request_permission`, tenant transaction/RLS modules: actual session identity, workspace discovery, IAM and persistent authority, independent of browser selection/storage.
- `backend/app/main.py:websocket_endpoint`: handshake/session/workspace authentication; every event and idle 30-second loop rechecks old token authority. Direct production WebSocket topology is not accepted by this audit.

## What the reported reason proves, and what it does not

`_complete_google_callback` checks state presence/length, then looks up `oauth_tx_<SHA256(returned-state)>`. `missing_transaction_cookie` means that exact named cookie did not exist in the backend's parsed callback request. This branch occurs **before ledger consumption or token exchange**. It does not prove cookie rejection, overwrite, Railway fault, Google configuration fault or a tenant/RLS failure.

| Finding | Classification | Evidence / remaining uncertainty |
|---|---|---|
| Matching callback cookie missing | Confirmed reported failure class; reproduced intentionally locally | Clearing transaction cookie produces the reason and no provider call; production request/response cookie trace unavailable. |
| Fixed-name overwrite in current code | Ruled out for ordinary parallel starts | Unique SHA-256(state) names; browser observed two pending cookies and reverse completion. Historical fixed-cookie defect was already corrected before this baseline. |
| Returned state differs from original request | Possible | Different state selects a different cookie name and can produce the same reason; no safe production correlation evidence supplied. |
| Set-Cookie absent/stripped/rejected in production | Possible | Current declarations and local proxy deliver it. Failed production response and Chrome blocked reason not available. |
| Host/path/profile/context mismatch | Possible | Host-only callback-path cookies require start/finish in compatible context; exact observed failed browser/redirect chain unknown. Never broaden cookie domain/path as a guess. |
| Abandoned or slow transaction expires browser cookie | Possible | Max-Age 600; valid cookie with expired ledger yields transaction_unavailable, but browser dropping expired cookie yields missing_transaction_cookie. Failed attempt timing unknown. |
| Browser limits/cleanup | Possible under many accumulated attempts; not observed | Each login adds one bounded cookie; successful/browser-failed callbacks clear only their own cookie; abandoned cookies expire naturally. Three starts passed. Capacity stress not run; do not assume a browser-specific count limit/root cause. |
| Network/IP binding | Absent in application validation | No IP/network/device binding; cookie context still matters. Independent real devices/networks require later acceptance. |
| Ledger loss on restart or consumed callback | Different failure when matching cookie remains | Ledger persisted in SQL; reopening repository passes. Missing/expired/consumed ledger produces transaction_unavailable, not missing-cookie by itself. Full deployed restart not performed. |
| Raw browser JSON errors | Confirmed baseline code defect, corrected | Browser navigation previously received raised HTTPException JSON. API clients still retain structured static diagnostics; HTML browser flows now recover safely. |
| Stale identity/workspace in authenticated tabs | Confirmed baseline behavior gap, corrected | Previous hook only bootstrapped/manual refresh/401. Focus/broadcast/poll browser checks and authoritative mismatch guard now pass. |
| Prior browser token remains active after switch | Confirmed baseline code behavior, corrected for presented token | New callback now revokes only the prior token in that request. Other device/profile sessions remain valid. |

SameSite Lax allows eligible cross-site top-level safe navigation; Secure requires HTTPS and HttpOnly prevents script access, not normal cookie delivery. This flow uses top-level GET callbacks, so third-party cookie blocking alone is not a demonstrated explanation. Browser policy/context still needs inspection. Sources: [MDN Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie), [Google web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server), [Chrome cookie diagnostics](https://developer.chrome.com/docs/devtools/application/cookies).

## Cookie and transaction contract retained

| Cookie | Host/domain | Path | Flags | Lifetime / deletion |
|---|---|---|---|---|
| `oauth_tx_<state digest>` | Domain omitted, browser-visible host only | `/api/v1/auth/google/callback` | HttpOnly; Secure on HTTPS config; SameSite=Lax | Max-Age 600; clear only matching transaction on success/browser failure. |
| `app_session` | Same host-only rule | `/` | HttpOnly; Secure on HTTPS config; SameSite=Lax | Max-Age 43200 (12h); server validates expiry/revocation; logout deletes same path/flags. |
| Legacy OAuth names | No new live values | Callback path | Matching deletion flags | Successful/browser-failed matching cleanup also removes old fixed names. |

State/cookie digests and expiry are in `oauth_transactions`; nonce/verifier remain in the HttpOnly cookie and process memory. Missing/wrong cookies cannot consume another transaction. Conditional DELETE requires correct digests and unexpired row, and occurs before Google calls. Denial/provider failure still consumes the matched transaction; retries start a fresh login. There is no auth-code replay/reuse for real Google. Browser fixture replay tests use only synthetic authorization codes.

Ledger cleanup runs when a new login starts; abandoned browser cookies expire after ten minutes. Callback-only cookie path means a login request cannot enumerate old callback cookies for cleanup; clearing every transaction would destroy concurrent starts. No blanket logout clearing or capacity-driven eviction logic was added. HTTP local development retains non-Secure loopback compatibility; production config remains HTTPS exact same frontend origin. Invalid configuration fails closed.

Vercel is the browser-visible origin for auth/REST. Backend uses explicit FRONTEND_URL and GOOGLE_REDIRECT_URI rather than forwarded host/proto. Local HTTPS proxy forwarded distinct Set-Cookie headers; real Vercel response delivery/caching and actual Railway configuration remain unverified this turn. Do not assign blame to a hosting provider from the missing-cookie reason alone.

## Corrections and coherent shared-profile behavior

1. **Safe browser recovery:** HTML Accept login/callback failures use fixed copy, not provider/state/code/error details. Valid configured callback failures redirect only to configured `/?auth=failed`; no caller-selected redirect or sensitive query is propagated. Invalid config returns a static 503 HTML page with a relative application link. JSON API clients preserve existing status/static codes/reasons. Matching cookie cleanup leaves unrelated pending transactions intact; current application session is not destroyed by a failed login. Referrer-Policy no-referrer on success/error recovery avoids callback-query leakage to the redirected page; auth no-store protections remain.
2. **Frontend recovery feedback:** Auth success/failure marker is captured before query stripping, including React's repeated effect setup. Login displays fixed safe failure guidance. It never copies backend/provider text, callback codes or state into UI. Login is user-triggered; failed exchange is not retried automatically.
3. **Shared account reconciliation:** BroadcastChannel sends only a `recheck` hint after success/logout. Other tabs call `/auth/me`; focus/visibility checks and a visible-tab 15-second fallback work without localStorage/BroadcastChannel. Background browser timer throttling can delay checks; no instantaneous universal-tab guarantee is made. Errors/expiry clear authenticated view. Quiet checks of the same identity keep the workspace mounted; changed user ID keys/remounts WorkspaceProvider and children to discard old workspace/run/HR/research state. Auth generation guards reject obsolete `/me` results.
4. **Server identity restriction:** Clients keep the expected tab user ID in memory and attach `X-Expected-User-Id` to application/workspace REST, exports and logout. `_authenticated_record` compares it against the **cookie-authenticated** user; mismatch returns 401 session_changed before workspace/business mutation. The header can only restrict; absent/spoofed header never authenticates or grants tenant permissions. `/me` omits the assertion so it can discover the new authoritative identity. A stale tab cannot use the new cookie to mutate/logout as its previous account. No automatic mutation retries are added.
5. **Presented session rotation:** Successful callback saves new opaque session then revokes the existing session token presented in that callback. Independent devices/profile tokens remain active. Existing websocket tokens are checked against server revocation; account remount closes/recreates frontend socket. Two overlapping callbacks may each create a valid session row if both requests carried the same previous token; no browser-family/session-group model was introduced. The last successfully delivered app cookie controls shared tabs; this is not global user-session revocation or atomic family rotation. Operations already authenticated/in flight are not retroactively undone.

A single profile shares one application cookie. Different Google identities in different tabs are **not independent sessions**; successful account switching changes the shared profile. Independent browser profiles/device contexts have independent cookie jars and can retain different identities. Tests model independent profiles with isolated Chrome contexts; real installed profiles/devices/networks remain acceptance work. Server-side session, IAM/HR permission and FORCE RLS authority remain unchanged.

## Required scenario matrix

| # | Scenario | Current local evidence / limitation |
|---|---|---|
| 1 | Fresh clean login | HTTPS Chrome fixture + backend tests pass. Mock Google only. |
| 2 | Login/logout/login | Chrome and backend pass. |
| 3 | Expired session | Chrome focus recovery + backend fresh-login tests pass. |
| 4 | Two simultaneous login tabs | Two pending actual browser navigations retain separate cookies; backend tests pass. Not a load/concurrent-worker stress test. |
| 5 | Reverse callbacks | Chrome/backend pass; last completion changes shared identity. |
| 6 | Different Google accounts, shared profile | Synthetic alpha/beta/gamma identity switch passes; independent identities are not promised in one profile. |
| 7 | Switch with previous authenticated tab | Broadcast and keyed provider reset observed; stale task/workspace/mutation/logout requests rejected in backend tests. |
| 8 | Independent profiles | Isolated Chrome contexts pass; real Chrome profiles/devices not tested. |
| 9 | Three consecutive attempts | Chrome/backend pass with fresh transactions. |
| 10 | Missing transaction cookie | Intentionally removed cookie: browser recovery + backend no-provider-call pass. Spontaneous production omission not reproduced. |
| 11 | Tampered state/cookie | Backend tests fail closed, no provider call. Browser recovery for tampered-cookie class covered by TestClient HTML tests. |
| 12 | Expired transaction | Backend forced ledger expiry fails closed; ten-minute real browser waiting not run. |
| 13 | Replayed callback | Chrome synthetic replay and restored-original-cookie backend replay fail closed. No real Google code replay. |
| 14 | Backend restart while pending | SQLite engine disposal/reopen + restored cookie test passes, showing persistent ledger consumption. Full server process/release/prod restart pending. |
| 15 | Lost login network | Chrome aborts callback before delivery then fresh login succeeds; mocked exchange network failure consumes attempt. Real provider outage not tested. |
| 16 | Slow callback | Local mock exchange delayed 0.3 seconds succeeds within TTL; timeout handling has mocked error coverage. Real Google/device slow-network acceptance pending. |
| 17 | Logout with other tab open | Chrome broadcast reconciliation; pending independent OAuth transaction remains valid. |
| 18 | Workspace API after account change | Backend old-user header rejected for task list/create, workspace list, logout; current-user view allowed. Actual Chrome bootstrap changes to new personal workspace. |
| 19 | Storage-restricted browser | Throwing localStorage/BroadcastChannel constructors: login, focus and periodic reconciliation pass. Cookies must still be allowed; fully blocked cookies fail safely. |
| 20 | HTML/proxy failure | Browser/API tests show safe connection recovery and no raw private proxy payload. Local fixture does not emulate all Vercel failures. |

## Exact verification evidence

Final targeted runs (Google/provider mocked; no full regression repeated):

| Selection | Result | Evidence |
|---|---|---|
| Auth/reliability/security/storage/bootstrap/RBAC | **105 passed, 0 failed, 0 skipped**, 2 dependency warnings | `docs/acceptance/oauth-reliability/backend-auth.txt` |
| Storage/migrations declarations/tenant/HR/research/recycle | **216 passed, 0 failed, 0 skipped**, 2 dependency warnings | `backend-audit.txt` |
| Optional local OAuth/HR/research PostgreSQL | **26 skipped**, 0 failed | `postgres-unverified.txt`; no restricted URL/credentials/schema provisioned. Skips are not FORCE RLS proof. |
| Frontend auth/routing/workspace/session sync | **52 passed, 0 failed, 0 skipped** | `frontend.txt` |
| Frontend HR/research/organization compatibility | **33 passed, 0 failed, 0 skipped** | `frontend-compatibility.txt` |
| Actual local Chrome HTTPS checks | **20 checks passed**, no blocked transaction cookie reasons observed | `browser-results.json`; artificial missing-cookie scenario clears it deliberately. |
| Frontend lint/build | Both pass | `lint.txt`, `build.txt`; 2 existing Fast Refresh warnings and >500kB bundle warning. |
| Syntax/whitespace | Python compile check and `git diff --check` pass | Final local check. |

Distinct backend passed total: **321**, frontend **85**, across non-overlapping selections; optional PG cases are separate skips. Backend warnings are Starlette/AnyIO alias deprecation and LangGraph serializer pending deprecation. The browser HTTPS helper serves REST only, with no websocket upgrade; socket console/connectivity in this fixture does not establish deployed WebSocket acceptance. An initial browser run timed out on missing-cookie feedback and exposed the repeated-effect defect; after correction all final checks passed. Initial bundled Chromium executable/version mismatch was resolved by using isolated installed Chrome (no download or user profile access). No failed test remains in final runs.

Safe screenshots: `account-switch.png` (synthetic account), `callback-recovery.png`, `proxy-recovery.png` in `docs/acceptance/oauth-reliability/`. No cookie values, callback queries, state, authorization codes, provider token or private records saved.

## Reproduction

From repository root, use existing Python/frontend dependencies and a separately available Playwright package; the browser script requires installed Google Chrome and temporary isolated contexts. Never run fixture endpoints on a public interface or import fixtures in application startup.

```sh
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_oauth_reliability.py backend/tests/test_oauth_portability.py backend/tests/test_google_auth_api.py backend/tests/test_browser_session_security.py backend/tests/test_auth_storage.py backend/tests/test_workspace_bootstrap_context.py backend/tests/test_rbac_api_enforcement.py -q
```

Frontend selection from `frontend/`:

```sh
node --test --test-concurrency=1 tests/session-sync.test.js tests/auth-simulation-ux.test.js tests/api-routing.test.js tests/workspace-switcher.test.js
npm run lint
npm run build
```

Browser fixture in separate local terminals (TLS key/cert are disposable, not production credentials):

```sh
PYTHONPATH=backend .venv/bin/python backend/tests/oauth_reliability_browser_fixture.py
```

From `frontend/`:

```sh
VITE_API_BASE_URL='https://127.0.0.1:8443' VITE_WS_URL='wss://127.0.0.1:8443/ws/live' npm run dev -- --host 127.0.0.1 --port 5178 --strictPort
```

From repository root:

```sh
openssl req -x509 -newkey rsa:2048 -nodes -keyout /private/tmp/fm-oauth-key.pem -out /private/tmp/fm-oauth-cert.pem -days 1 -subj '/CN=127.0.0.1'
node backend/scripts/oauth_local_https_proxy.cjs /private/tmp/fm-oauth-key.pem /private/tmp/fm-oauth-cert.pem
```

Then in another terminal, point `FM_PLAYWRIGHT_MODULE` to the available Playwright module directory if it is not normally resolvable:

```sh
node backend/scripts/oauth_browser_acceptance.cjs /private/tmp/fm-oauth-browser-results.json
```

Stop all three servers after acceptance; fixture shutdown disposes/removes temporary SQLite. Remove exact generated TLS files after proxy shutdown. Chrome contexts are ephemeral and closed by the runner. Existing application SQLite files are never selected by fixture. Reproduction script does not start real Google/provider calls or change deployed settings.

## Precisely missing production evidence

Capture a **new** attempt in the affected profile without retrying an old code or copying raw callback URLs/cookies/HAR. Preserve network activity in DevTools and record only:

1. Browser/version, profile vs incognito/embedded context, device/network class and timing between start/callback; browser-visible hosts/paths (no query).
2. Login response status/deployed frontend+backend versions, no-store/cache status, whether matching unique Set-Cookie was present. Record flags/path/domain/expiry, accepted/rejected and Chrome's blocked reason. Do not retain cookie name suffix/value or state.
3. Whether the browser's jar retained that cookie after redirect, and whether callback request attached the matching name (boolean only); whether the callback returned the same state as that attempt (compare locally, save boolean only).
4. Whether Vercel received/forwarded matching Cookie and passed backend Set-Cookie headers; correlate a nonsensitive request ID and safe static failure reason, not credential/query values.
5. Which tabs/attempts/accounts were pending, any logout/account change, context switch, cookie-clearing/privacy extension or host alias use. Verify exact registered redirect and active environment through authorized operator checks without extracting secrets.

This isolates missing delivery vs rejection vs expiry/context mismatch vs forwarded-header loss vs state-name mismatch. Do not assume Railway caused it. Public previous redirect tests alone cannot prove a failed browser callback path. Source: [Chrome cookie diagnostics](https://developer.chrome.com/docs/devtools/application/cookies).

## Prioritized next steps and later release sequence

| Priority | Remaining task | Reason | Dependencies | Acceptance criteria |
|---|---|---|---|---|
| P0 | Redacted failed-profile cookie trace | Exact production omission remains unknown | Affected browser and authorized operator metadata | Start-response acceptance and callback delivery booleans/reason/host/timing establish cause without secrets. |
| P0 | Approve and accept coordinated OAuth release | Local corrections are not deployed | Separate release authorization; deployed-version/config verification; existing backup/rollback plan | Fresh login/logout/relogin, reverse tabs/switch, stale API denial, independent real profiles/devices/networks pass via Vercel. |
| P1 | Restricted local PG reacceptance + production catalog/role/backup inventory | 26 fresh SQL tests skipped; live architecture unverified | Approval before temporary restricted login; separate authorization for production read/operations | Zero-skip targeted ledger/HR/research/RLS tests; non-bypass live role and expected schema; tested recovery plan. |
| P1 | Define retention for review-associated AI runs | JSON references do not prevent evidence purge | Explicit audit retention requirement | Referenced AI output stays inspectable or clearly recorded authorized retained export/deletion policy. |
| P2 | Read-only Research Lab demonstration/empty-state guidance | Disabled execution plus empty history can confuse | Existing fixture report; no live gate enablement | Labelled fixture history/report usable without provider calls or fabricated production runs. |
| P2 | Dedicated JD export/package only if needed | Approval is implemented; distribution isn't | Defined academic/product export scope | Exact approved revision and source/decision history export under HR authorization. |

**Safest future deployment order (not authorized/performed here):**

1. Review local commits and separately authorize publication/releases. Keep Railway autodeployment disabled. Confirm backend supports schema 14, existing ledger privileges, correct persistent PostgreSQL binding, exact Vercel callback/frontend origin, backup/restore readiness and rollback compatibility. No automatic migrations/Console changes as a guess.
2. With Vercel's main auto-deploy controlled by the operator (or another explicitly approved publication method), deploy the backend correction **first**, without publishing the frontend changes ahead of it. New backend accepts old clients because the identity assertion is additive/optional. Existing transaction format is unchanged, so there is no new cookie-format migration. SQL schema stays 14.
3. Validate Vercel-routed login/callback/me/logout/no-store/cookie delivery against the new Railway backend. Then publish/deploy the frontend after confirming new backend serves the header restriction. Frontend-first could attach a header an old backend ignores, leaving stale-view protection incomplete.
4. Run the complete real browser/device matrix, especially account-switch workspace operations and expired/revoked recovery. If backend cannot be independently published without main triggering Vercel, obtain an operator-controlled Vercel hold/manual ordering plan before pushing. Do not enable Railway autodeployment. Rollbacks must retain the existing V14/ledger-compatible backend and account for pending/new sessions; older schema-13 binaries are not compatible rollback targets.

Stop after local investigation, secure corrections, tests, documentation and local commits. Production acceptance is still required.
