# Task 1 — Authentication and simulation UX acceptance

Local acceptance on 9 October 2026. Starting branch: `main`. Starting HEAD: `1fcc18b4db4279cdd7f6fc3124c5af6da76bc7b7`. The initial working tree contained only untracked `AGENTS.md`. One local commit is authorized after validation; no push or deployment is part of this task.

## Confirmed defects and corrections

- Login displayed the same authentication-service error for unrelated failures and offered no retry. Fixed copy now distinguishes server outages, network interruption, timeout, unexpected responses, unavailable account access, expired sessions and other invalid sessions. Server messages and OAuth diagnostics are not rendered in these screens. Anonymous sign-in remains a normal state.
- The auth client discarded structured session-expiry/revocation codes. It now preserves those codes. A parsed API 401 ends the authenticated view and provides sign-in guidance without automatic redirects or mutation retries. HTML/proxy 401 responses cannot masquerade as expired sessions. Stale auth-check responses are ignored.
- Initial workspace bootstrap showed application controls before workspace access resolved, and errors lacked an effective primary recovery action. A shared loading/error screen now gates initial workspace access and offers retry. A successful retry resolves only server-discovered workspace choices.
- Sign out lacked progress and failed without visible recovery. It now disables duplicate requests, announces progress, retains the authenticated view when logout is unconfirmed and offers retry through the existing Sign out action.
- Optional saved-run selection accessed browser storage without guards. Storage denial no longer prevents workspace use; server authority remains unchanged.
- New simulation form had a short task input, ambiguous required/optional hierarchy and technical primary labels. It now has a readable six-row task input, guidance on goals and output format, numbered task/mode/context steps, simpler mode subtitles and a sticky action row. Context and individual specialist controls remain available in subordinate disclosures. Single, Fixed, Adaptive, specialist selection, registered datasets and uploads use their existing API payloads.
- A creation acknowledgement disappeared when a stale list refresh omitted it. Locally acknowledged omissions now use the existing tenant-scoped task-detail API until the list catches up or detail confirms 404. Network/server/permission failures cannot pretend to confirm removal. Historical list omissions still remove records normally. Responses from an old workspace cannot inject evidence into the current one.
- The graph dominated the workspace ahead of results, while failure and pending output shared a generic empty message. Recorded run status and active/completed stages now precede the primary reading pane; final results precede a collapsed graph/routing disclosure. Failed-stage controls open actual persisted evidence. No resume operation is advertised without a capability contract.
- Changing or creating runs retained an unrelated detail view. These actions now restore the primary Output view. Empty workspaces hide run-only detail controls and the Execution events action.
- Repeated connection warnings obscured the workflow. Connection diagnostics remain in the shared disclosure; an available workspace with polling shows `Ready · automatic refresh`. Simulation-data failures remain distinct from backend reachability. Retry loading now has a disabled pending state.
- A later tablet stylesheet overrode phone navigation and hid labels. Phone navigation is now a readable stacked two-column list. Workspace selector focus, shared disabled buttons and caller-supplied Button classes are corrected. Plain-text final output no longer inherits a 360px nested scroll cap.

The existing Modal, RunPicker, TaskDetailsPanel, OutputViewer and design tokens were inspected and reused. Modal focus containment and return focus remain intact. Raw/Rendered views, clipboard copy, focus reading, intermediate outputs, routing, exports and historical evidence remain available. Provider text, persisted outputs and output normalization logic were not rewritten.

## Exact final validation

| Check | Result |
| --- | --- |
| Frontend regression (`npm test`) | 218 passed; 0 failed, cancelled, skipped or todo |
| Frontend lint (`npm run lint`) | Exit 0; 0 errors; 2 existing Fast Refresh export warnings in AppShell and SimulationContext |
| Production build (`npm run build`) | Exit 0; 2,033 modules; JS 533.97 kB, gzip 159.75 kB; one >500 kB chunk warning |
| Focused backend compatibility | 59 passed; 0 failed/skipped; 2 dependency deprecation warnings |
| Browser acceptance | 71 checks passed; completed=true; 0 uncaught errors; 0 external/provider requests |
| Whitespace validation (`git diff --check`) | Passed |
| AGENTS.md integrity | SHA-256 `a5f46def185ce9e844d9d468912f3fbee4dbf2d8f14f08c91c02553352e87efd`; untouched, untracked, excluded from staging |

Focused backend command from the repository root:

```sh
.venv/bin/python -m pytest backend/tests/test_google_auth_api.py backend/tests/test_oauth_portability.py backend/tests/test_workspace_list_api.py backend/tests/test_workspace_bootstrap_context.py -q
```

These tests isolate local SQLite state and mock Google/provider calls. The warnings were the anyio BlockingPortal alias deprecation and LangGraph serializer allowed_objects pending deprecation. The full backend suite was not run because backend code did not change.

Added tests: `auth-simulation-ux.test.js` (18), `acknowledgedRuns.test.js` (5), and three hook race/loading tests in `simulationData.test.js`. Updated composer and readiness expectations. Existing API routing, authorization, workspace switching and output preservation tests remain in the final frontend pass.

## Browser evidence

`browser-results.json` contains every check and observed warning. Chromium ran the local in-memory fixture at 1440×1000 and 390×844, plus an independent context at 1280×800 with browser storage deliberately denied. All browser network requests were restricted to loopback. Three task submissions and one reference upload were mock acknowledgements only; no backend or model executed them.

Verified: safe login error/retry; anonymous, expired and denied-account states; network interruption; auth/workspace loading; workspace retry; empty workspace; all execution-mode controls; datasets and reference upload; creation loading and focus; queued/running/completed snapshots; Raw/Rendered, clipboard and focus reading; failed-stage inspection; graph/routing access; validation rejection and unknown creation outcome; failed logout/retry; session expiry during workspace API use; simulation-load retry feedback; phone overflow; keyboard modal boundaries; independent-context workspace access and authorized selection with storage denied.

Screenshots were visually inspected for layout, readability, hierarchy and overflow:

- `login-retry-desktop.png`, `workspace-retry-desktop.png`, `empty-desktop.png`
- `composer-desktop.png`, `composer-context-desktop.png`, `composer-mobile.png`
- `running-desktop.png`, `completed-desktop.png`, `completed-mobile.png`, `failed-desktop.png`

Observed browser warnings: React Flow nodeTypes/edgeTypes warning under the existing StrictMode wrapper, and fixture WebSocket closure before connection establishment. The graph rendered and its controls worked. The fixture intentionally does not provide live WebSocket service. Expected 401/403/422/503 and aborted-network diagnostics from negative cases are retained in the JSON; they are not uncaught application errors.

Reproduction: run `node frontend/tests/fixtures/workbenchPreview.mjs /private/tmp/fm-task1-ux-fixture.json --composer-fixture`, then `node frontend/tests/browser/task1-ux.mjs`. Set `PLAYWRIGHT_MODULE` and, if needed, `PLAYWRIGHT_EXECUTABLE` to available local installations. The fixture uses an isolated dependency cache, rejects unsupported writes and never forwards requests to a backend/provider. Stop the preview after acceptance.

## Limits and outstanding work

This is frontend/local acceptance. It does not claim to repair a server-side OAuth fault or establish production availability. Live Google OAuth/provider execution, real cross-device/network access, production PostgreSQL/RLS and real WebSocket transport were not exercised here. Backend code, schema 14, migrations, routing, production configuration, OAuth settings and authentication cookie/state/one-time transaction protections were not changed. No production database, secrets, deployment, push, branch, PR or history rewrite was involved.

OAuth login/callback failures navigated directly to backend endpoints still use their existing backend response behavior; this task improves SPA session/bootstrap presentation. A browser-friendly callback failure destination would require a separate reviewed backend authentication change. Bundle splitting and the React Flow warning remain follow-up work. Organizations, Research Lab and HR Hiring received only shared UI behavior/styles and frontend regression coverage, not page redesign or browser acceptance.

## Specific next-pass issues (code-inspected)

- Organizations: reconcile the contradictory created-organization copy that says to share a join code but then points to one-time invitations; consolidate its separate button/input/error styles with the shared components; give membership/action errors consistent safe recovery and focus behavior.
- Research Lab: disable/explain `Open run evidence` until its task is available (the current callback silently does nothing without task data); add an initial-load retry; explain all invalid configuration reasons next to the disabled start action; align its raw buttons/forms and mobile report/table layouts with the shared design system.
- HR Hiring: mark required and optional record/source fields visibly; replace one-row long-form textareas with appropriate readable sizes; make selected revision, read-only state and revision conflict recovery prominent near Save while preserving all existing recruiter/reviewer/approver authority.

The complete scoped file list is in `changed-files.txt`.
