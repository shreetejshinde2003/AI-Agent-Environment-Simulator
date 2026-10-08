# FMProject frontend

React/Vite workspace UI backed by the authenticated FastAPI API. The default UI
uses saved application data. Google OIDC signs users in; workspace switching
selects a private Personal Workspace or an accessible Organization.

## Local setup and validation

```sh
npm ci
cp .env.example .env
npm run dev -- --port 5173 --strictPort
npm test
npm run lint
npm run build
```

Use Node 22.12+ on the 22.x line, or a version satisfying the locked tools'
`^20.19.0 || >=22.12.0` requirement (prior acceptance used Node 25.5.0).
Run these commands from `frontend/`. Copy the template only when `.env` is absent.
Open **http://localhost:5173**. `--strictPort` prevents an unnoticed port/origin change.

Frontend tests, lint, build, login and legal-page rendering need no production
credentials. Protected workspace pages require real sign-in with an authorized
Google development client; GitHub access does not grant OAuth credentials and demo
mode does not bypass authentication. Follow the [root onboarding guide](../README.md#local-development)
for local SQLite/backend installation and exact localhost callback registration.

Vite has no API proxy. Development REST, auth and workspace requests go directly to
`VITE_API_BASE_URL` (default `http://localhost:8000`) with session cookies;
`VITE_WS_URL` optionally overrides `/ws/live`. Workspace requests carry
`X-Workspace-Id`. Keep hostnames consistent and configure backend `CORS_ORIGINS`
and `FRONTEND_URL` for the browser origin. Never put secrets in `VITE_*` variables.
Restart Vite after environment changes. Use the development server for local API
work; preview uses production-origin auth routing without a backend proxy.

If the frontend fails to start, check Node and `npm ci` output. If it loads but API
requests fail, check `/health`, the Network panel's request origin, backend port,
trusted CORS origins and cookies. An anonymous `/auth/me` 401 is expected;
`google_auth_not_configured` 503 means backend OAuth settings are incomplete.
Ollama is not part of the active runtime and does not fix either error.

## Implemented pages

- Live Simulation: Single, Fixed, Adaptive and individual specialist execution;
  recorded flow, stage evidence, inspector, events and saved-run selection.
- Simulation History: workspace-scoped saved runs, exports and terminal-run recycling.
- Agents: six executable system agents and a bounded text Agent Builder with
  immutable saved revisions, owner/admin management and member execution.
- Organizations: creation/join, IAM member management and separate HR human roles.
- Recycle Bin: manager list/delete/restore and owner-only evidence-preserving purge.
- Messages, Logs and Event History: persisted evidence, with no claimed execution replay.
- HR Hiring: requirements, knowledge, human drafts, exact source/revision navigation,
  proposal-only AI evidence and revision-pinned human review/approval.
- Research Lab: seven versioned cases, repetitions, per-case descriptive mode
  comparisons, individual evidence, human rubric history and report preview/export.
- Settings and legal/sign-in pages.

Route-level UI lives in `src/pages/`, reusable controls in `components/common/`,
execution views in `components/dashboard/`, connection/data behavior in `hooks/`,
and authenticated request access in `services/`. Reuse `src/index.css` tokens.

`useLiveSocket` re-reads authoritative REST data on events and reconnects; it does
not treat notifications as an independent evidence store. Simulation reads use
workspace generations to discard obsolete responses, including A to B to A
switches; previous workspace evidence is hidden before effect cleanup. Backend IAM remains
authoritative when permissions change. Custom agents have one saved text stage;
they cannot configure tools, providers, credentials, topology or durable graph resume.

## Verification boundaries

Frontend tests use Node's test runner and mocked request responses. The explicit
`backend/tests/agent_builder_browser_fixture.py` supplies a disposable localhost
browser session with deterministic mocked provider responses; it is never part
of the production API. Browser acceptance proves UI/API integration, not live Groq.
See [Phase 10 final acceptance](../docs/PHASE10_ACCEPTANCE_REPORT.md) and
[the disposable final demo fixture](../docs/FINAL_DEMO_GUIDE.md).

Production builds deliberately use the frontend origin for `authClient` and
`workspaceClient`, while other requests may use `VITE_API_BASE_URL`. The checked-in
Vercel configuration proxies only `/api/v1/auth/*`; its catch-all can send workspace
API requests to `index.html`. Resolve and verify this proxy/cookie/WebSocket topology
before production rollout. A successful local Vite check does not validate it.
Do not put provider credentials in frontend environment variables.
