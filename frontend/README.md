# FMProject frontend

React/Vite workspace UI backed by the authenticated FastAPI API. The default UI
uses saved application data. Google OIDC signs users in; workspace switching
selects a private Personal Workspace or an accessible Organization.

## Local setup and validation

```sh
npm install
npm run dev
npm test
npm run lint
npm run build
```

Start the API separately as described in `../backend/README.md`. Vite defaults
to port 5173. `VITE_API_BASE_URL` selects the REST API origin;
`VITE_WS_URL` optionally overrides its `/ws/live` WebSocket URL. Requests include
opaque session cookies and workspace APIs carry `X-Workspace-Id`. Configure the
backend's trusted `CORS_ORIGINS` for the actual browser origin.

## Implemented pages

- Live Simulation: Single, Fixed, Adaptive and individual specialist execution;
  recorded flow, stage evidence, inspector, events and saved-run selection.
- Simulation History: workspace-scoped saved runs, exports and terminal-run recycling.
- Agents: six executable system agents and a bounded text Agent Builder with
  immutable saved revisions, owner/admin management and member execution.
- Organizations: creation/join, IAM member management and separate HR human roles.
- Recycle Bin: manager list/delete/restore and owner-only evidence-preserving purge.
- Messages, Logs and Event History: persisted evidence, with no claimed execution replay.
- Settings and legal/sign-in pages.

Route-level UI lives in `src/pages/`, reusable controls in `components/common/`,
execution views in `components/dashboard/`, connection/data behavior in `hooks/`,
and authenticated request access in `services/`. Reuse `src/index.css` tokens.

`useLiveSocket` re-reads authoritative REST data on events and reconnects; it does
not treat notifications as an independent evidence store. Backend IAM remains
authoritative when permissions change. Custom agents have one saved text stage;
they cannot configure tools, providers, credentials, topology or durable graph resume.

## Verification boundaries

Frontend tests use Node's test runner and mocked request responses. The explicit
`backend/tests/agent_builder_browser_fixture.py` supplies a disposable localhost
browser session with deterministic mocked provider responses; it is never part
of the production API. Browser acceptance proves UI/API integration, not live Groq.
See [Phase 4 final acceptance](../docs/PHASE4_FINAL_ACCEPTANCE_REPORT.md).

Production builds deliberately use the frontend origin for `authClient` and
`workspaceClient`, while other requests may use `VITE_API_BASE_URL`. The checked-in
Vercel configuration proxies only `/api/v1/auth/*`; its catch-all can send workspace
API requests to `index.html`. Resolve and verify this proxy/cookie/WebSocket topology
before production rollout. A successful local Vite check does not validate it.
Do not put provider credentials in frontend environment variables.
