# OAuth portability correction — local acceptance

Starting HEAD: `cd4bee22f404ce373331cbd4876d25fe402e9407`, branch `main`.
Production release remains paused. No production configuration/database changes,
Google token exchange, paid AI calls, push or deployment occurred.

## Evidence and diagnosis

The Android failure reported `invalid_oauth_state` at the Vercel callback. The
callback query is intentionally omitted because it contains temporary credentials.
On 2026-10-08, two read-only public login requests returned 302 to Google with:

- callback `https://ai-agent-environment-simulator.vercel.app/api/v1/auth/google/callback`;
- three host-only Secure/HttpOnly/SameSite=Lax cookies, callback path, Max-Age=600;
- different state per request, Vercel cache MISS and
  `Cache-Control: public, max-age=0, must-revalidate`.

Cookie values, state and authorization codes were not printed or saved. The Google
redirect was inspected without signing in or exchanging a code.

| Cause | Classification | Evidence |
|---|---|---|
| Missing/mismatched browser state | CONFIRMED failure class | The old handler returns the observed code only for absent query/cookie state or unequal values; failed-device cookie presence is unknown. |
| Login cookie overwrite | CONFIRMED code defect, POSSIBLE cause of Android failure | Every old login overwrote the same three cookie names; parallel/repeated starts invalidated earlier callbacks. |
| Callback host mismatch | RULED OUT for the reported/current flow | Both reported callback and inspected redirect use Vercel. Stale custom-domain/direct-backend configurations remain possible elsewhere. |
| Cookie expiry/context switch/blocking | POSSIBLE | The old browser expiry was ten minutes; the failed-device request headers and browser context were not available. |
| Cached OAuth redirect | POSSIBLE, not observed | Old auth responses did not explicitly forbid caching; inspected requests were MISS with fresh state. |
| IP/network/device binding | RULED OUT in application code | No IP, network or device allowlist participates in OAuth state verification. |
| Process-memory loss | RULED OUT as old state-storage cause | Old state was exclusively in browser cookies, not a process dictionary. |
| Google redirect registration mismatch | RULED OUT as explanation of this error | The application callback was reached; wrong registration normally fails at Google. Exact current registration still requires operator verification. |
| Existing session hiding a login defect | LIKELY explanation of apparent desktop success | A valid database-backed session can bootstrap without another OAuth transaction; not proof of the failing device's cause. |

The exact cause of the Android failure is not established. Local fixes address
confirmed transaction defects; they are not a claim that real-device production
portability now passes.

## Flow and authoritative functions

Before: `frontend/src/pages/Login.jsx` links to `AUTH_LOGIN_URL` in
`frontend/src/services/authClient.js`. Production `apiConfig.js` uses relative
REST. `frontend/vercel.json` rewrites login to Railway FastAPI.
`auth.google_login()` generates random state/nonce/PKCE, sets three fixed-name
cookies and redirects to Google. Google returns to the configured callback.
`auth.google_callback()` compares state against its cookie, exchanges the code
using `_exchange_code()`, verifies audience/signature/issuer/expiry with
`_verify_google_id_token()`, verifies nonce and email, saves the user/personal
workspace and a hashed opaque session through `Repository`, sets `app_session`,
and redirects to configured `FRONTEND_URL/?auth=success`. `auth.me()` validates
session expiry/revocation and active user; logout revokes it and clears its cookie.

After: the public path is unchanged. Each login now has a distinct
`oauth_tx_<SHA256(state)>` cookie containing base64url nonce/PKCE material. A new
`oauth_transactions` table holds only state digest, cookie digest and expiry.
Callback conditionally deletes the matching unexpired record before any Google
call, so expiry and one-time consumption are server-enforced and competing
callbacks cannot both proceed. Wrong/missing cookies cannot consume another
transaction. Denied/provider-failed attempts are also consumed; start a fresh
login to retry. Other pending browser logins remain valid. Successful completion
clears only that transaction and old legacy OAuth cookie names.

The ledger is pre-authentication data with no user/tenant identity yet, like the
existing authentication bootstrap domain, not tenant execution data. No public
API exposes ledger records or enables arbitrary deletion. Digests are not bearer
credentials without the matching cookie. Expired ledger rows are cleaned on new
login; unused browser cookies expire after ten minutes.

## Cookie, origin, proxy and persistence contract

| Cookie | Domain | Path | Secure | HttpOnly | SameSite | Max-Age |
|---|---|---|---|---|---|---|
| Old state/nonce/PKCE | omitted, host-only | `/api/v1/auth/google/callback` | HTTPS config | yes | Lax | 600 |
| New transaction | omitted, host-only | `/api/v1/auth/google/callback` | HTTPS config | yes | Lax | 600 |
| App session after correction | omitted, host-only | `/` | HTTPS config | yes | Lax (previously None on HTTPS) | 43200 |

No explicit Expires is set for live cookies; deletion sets Max-Age=0/Expires.
Browser-visible Set-Cookie responses belong to Vercel despite execution on
Railway. Google returns by top-level GET to that same Vercel host; REST and logout
also use it. Sharing host-only cookies with Railway is unnecessary.

State/cookie material is not a signed token; authoritative digests bind it to the
database transaction. No new signing secret is needed. Cookies/ledger can survive
browser/process restart within the TTL if the browser retains its cookie jar.
Multiple instances require the same application database. New networks do not
invalidate state. Switching browsers/devices midway has no matching cookie and
must fail closed; start and finish on each device independently.

Callback, token-exchange redirect URI, frontend destination and Secure decision
use explicit configuration, not Host/X-Forwarded-Host/X-Forwarded-Proto. A public
callback must be HTTPS, exactly `/api/v1/auth/google/callback`, and on the
configured frontend origin; query/fragment/userinfo/unrelated redirect targets
are rejected. Separate loopback API/frontend ports remain supported locally.
No trusted-proxy expansion or arbitrary forwarded-host trust was introduced.

Backend and Vercel auth responses explicitly forbid browser/CDN caching, including
errors, `/me` and logout. Uvicorn auth access logs redact query strings. Platform
proxy logs are outside this code's control and need an operator review without
copying callback queries. Invalid-state errors expose only a static reason:
missing/invalid state, missing transaction cookie, or unavailable transaction.

Schema stays 14 because this release is still unreleased. Metadata initialization
additively creates `oauth_transactions` and its expiry index for existing V13/V14
SQLite/PostgreSQL databases. Existing users, sessions, workspace rows, tenant RLS
and invitation history are unchanged. Production startup now also requires CREATE
and ledger SELECT/INSERT/DELETE rights. Restricted PostgreSQL acceptance for this
new table has not run; its optional local test is skipped without credentials.
Old schema-13 code still cannot restart against schema 14. Pending pre-deploy OAuth
transactions must be restarted after deploying this changed transaction format.

## Required later configuration/acceptance

Google Cloud Web application OAuth client: verify the existing client registration
contains exactly:
`https://ai-agent-environment-simulator.vercel.app/api/v1/auth/google/callback`.
Google requires an exact redirect match. Verify audience/consent publishing policy
for intended users; testing-only account restrictions are unrelated to device
allowlisting. No Google setting was changed.

Railway variable contract:
- `GOOGLE_CLIENT_ID`: the matching Google Web application client identifier.
- `GOOGLE_CLIENT_SECRET`: its matching private backend secret; never a VITE value.
- `GOOGLE_REDIRECT_URI`: the exact Vercel callback above (observed live today).
- `FRONTEND_URL`: `https://ai-agent-environment-simulator.vercel.app`.
- `CORS_ORIGINS`: include that frontend origin for mutation-origin validation.
- `DATABASE_URL`: persistent, verified application PostgreSQL binding.

These require verification, not blind replacement. No new secret/environment
variable is introduced. Vercel must later deploy the unchanged API rewrites and
new auth no-store headers; no VITE variable or direct Railway auth URL is needed.
Configuration/deployments require separate approval under the paused runbook.

After controlled deployment, independently test owner's desktop/current network,
Android Chrome/mobile data, fresh/incognito browser, and teammate's browser/other
network. For each: public Vercel URL → Google sign-in → Vercel callback → app →
`/api/v1/auth/me` 200 → personal/authorized workspace → logout → `/me` 401 →
re-login. Start and finish in the same browser context; no device allowlist.
Also test two concurrent login tabs, reload and app restart. Record only safe
status/reason/host metadata. Do not copy callback codes/state/cookie values.

## Validation

- Focused auth, storage, origin and isolation tests: **63 passed, 1 skipped, 0 failed**, 2 dependency warnings. The new PostgreSQL case requires the existing restricted local test URL; no credentials/roles were created.
- Final full backend regression: **800 passed, 101 skipped, 0 failed**, 2 dependency warnings, 69.68 seconds. Skips are environment-gated acceptance, not PostgreSQL/RLS proof. The initial full run found a missing isolation classification (799 passed, 101 skipped, 1 failed); after the confirmed correction, focused tests and one final full rerun passed.
- Frontend routing/auth tests: **25 passed**. Full frontend suite: **192 passed, 0 skipped, 0 failed**.
- Lint and production build pass. Existing warnings: two Fast Refresh declarations and a >500 kB bundle. Compileall, pip check and git diff --check pass; pip reports an inaccessible cache warning, not a dependency failure.
- Google exchange/verification is mocked in all local tests. No physical-device acceptance was performed locally. Live read-only evidence above verifies redirect/cookie metadata, not Google callback success.

## Paused coordinated-release blockers

Railway hold mechanism; production DATABASE_URL binding; application role,
ownership/DDL and live RLS inventory; complete backup/restore readiness; safe old
backend maintenance/removal procedure all remain pending. Railway's inspected
current plan blocks native backup creation without Pro. Checkpoint bridge/runtime
and direct Railway WebSocket authentication remain separately gated. No push or
deployment is authorized by these local results.

Google reference: [Web-server OAuth redirect/state requirements](https://developers.google.com/identity/protocols/oauth2/web-server).
