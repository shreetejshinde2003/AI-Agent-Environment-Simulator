# Project state

- **Current release candidate:** Phase 10 baseline plus pre-release UX/output consolidation; no Phase 11. Operational schema 14 after the local product correction below.
- **Validation:** frontend 158 passed, 0 failed/skipped; lint/build pass. Backend full regression 752 passed, 84 restricted PostgreSQL/checkpoint cases skipped; final focused contract/storage regression 98 passed. Compileall and diff checks pass. Browser: four requests in each of Single/Fixed/Adaptive passed with mocked providers; eight main destinations and contextual/accessibility workflows checked.
- **UX/output consolidation:** eight navigation destinations; full-width final reading; contextual handoffs/events/history stepping; immutable original request and bounded subordinate handoffs; versioned prompts and explicit format-problem evidence; authoritative run actions. Soft delete retains raw evidence; explicit owner purge now removes it under the policy below.
- **Deployment:** local only. Nothing pushed/deployed; Railway untouched; production graph runtime remains disabled.
- **Live research:** not run. Fixture acceptance proves plumbing and presentation, not live model fidelity, superiority or statistical conclusions. Historical benchmark outputs/reports remain unchanged.
- **Academic report:** project/demo guides updated. Final academic report/PPT and independent human evaluation remain separate work.
- **Unresolved gates:** production checkpoint cleanup provisioning and WebSocket topology, live-provider format/semantic fidelity and controlled research approval, production tenancy/proxy/OAuth/restart acceptance, academic deliverables.
- **Next action:** review this local release candidate and plan explicitly authorized release-candidate checks. See [acceptance evidence](UX_OUTPUT_CONSOLIDATION_ACCEPTANCE.md).

## Local post-deployment product correction — 2026-10-08

The subsequent [local OAuth portability correction](OAUTH_PORTABILITY.md) adds
independent, database-backed one-time login transactions and auth no-store headers
to the unreleased schema-14 candidate. Real-device OAuth and new-table PostgreSQL
acceptance remain pending. Coordinated deployment stays paused on its previously
identified binding, role/RLS, backup, hold and maintenance blockers.
Final OAuth-candidate validation: 800 backend tests passed with 101 environment
skips; 63 focused auth/security tests passed with one PostgreSQL skip; 192 frontend
tests passed. Lint/build/compileall/dependency/diff checks pass with documented
existing warnings. No new live PostgreSQL or real-device OAuth result is claimed.

The current local candidate completes owner-confirmed execution-evidence purge, custom-agent archive, managed one-time invitations, state-aware member controls, readable readiness diagnostics and a usable Research Lab entry. Schema 14 adds invitation history. The seven synthetic benchmark definitions now ship inside the backend package. Nothing was pushed or deployed. Earlier reports below describe their historical validation snapshots; the changed retention/invitation policies supersede those earlier product assumptions.

Final local acceptance: 776 backend regression tests passed (99 environment-gated skips in that run), 62 distinct focused PostgreSQL/checkpoint cases passed separately, and 191 frontend tests passed. Browser workflows and temporary-resource cleanup passed. Lint/build/compileall/dependency/diff checks pass; remaining warnings and release gates are documented.

See [current behavior and acceptance](POST_DEPLOYMENT_PRODUCT_CORRECTIONS.md) for exact validation, fixture limitations, checkpoint cleanup prerequisites and remaining production gates.

## Local production REST routing correction — 2026-10-08

Starting HEAD: `16173864f0c32533b8e6b87e5e151c9adee1a791`, branch `main`.
Production deployment remains pending; this correction is one local commit only.

Previously auth used the Vercel rewrite, workspace discovery fell into the SPA,
and general REST could go directly to Railway via `VITE_API_BASE_URL`. The intended
REST contract is now browser → same-origin `/api/v1/*` → Vercel rewrite → Railway.
The generalized rule precedes `/health` forwarding and the frontend fallback;
the fallback explicitly excludes `/api` paths. The existing public upstream is
retained. Auth, workspace, general REST, uploads and exports share `apiConfig`.
Development retains explicit `VITE_API_BASE_URL` or localhost:8000.

JSON clients check media type, report controlled HTML/malformed JSON errors with
status/path/type metadata, strip query values and never echo response bodies or
credentials. Non-JSON create acknowledgements retain an unknown admission outcome
to prevent unsafe repeat submissions. Backend JSON errors retain their status/code/message. Anonymous JSON
401 and logout 204 remain supported. Export media types are checked separately.
Health requires the expected JSON status. The UI separately shows backend
reachability, workspace readiness and live events. Run creation waits for
workspace and protected REST data; workspace failure is not endless loading.

Final local validation: **184 frontend passed, 0 failed, 0 skipped**; focused new
routing/parser/status coverage **24 passed**; affected backend auth, session,
workspace admission and WebSocket authorization **35 passed, 0 skipped**, with
2 dependency deprecation warnings. Lint passed with 2 existing Fast Refresh
warnings; production build passed with one >500 kB chunk warning. Diff check passed.
Backend Python code did not change: compileall/full backend/PostgreSQL acceptance
were not required or rerun.

Browser acceptance used the final production build, a localhost rewrite-contract
proxy and the existing temporary SQLite/authenticated fixture with mocked SDK
output. Sign-in bootstrap, workspace discovery/selection, 42 seeded history rows,
create-run modal, a new Single run admission/completion (43 rows, fixture output
`42`), final-build reload/restoration, injected HTML workspace failure, clear status
labels, disabled creation during failure and recovery all passed. This is local
proxy/fixture evidence, not deployed Vercel, real OAuth or live model validation.
Evidence: [completed run](acceptance/api-routing-local-run.jpg) and
[controlled HTML error](acceptance/api-routing-html-error.jpg).

WebSocket assessment: `backend/app/main.py` authenticates `/ws/live` using the
opaque session cookie and checks origin/workspace access continuously. Auth cookies
are host-only (no Domain). A Vercel cookie cannot authenticate direct Railway WSS.
The existing separate `VITE_WS_URL` transport remains; no tokens, weaker auth or
WebSocket proxy were introduced. REST polling remains functional with live events
offline. An approved compatible WebSocket deployment design is still a release gate.

See [release routing steps and reproduction](RELEASE_READINESS.md#local-routing-correction--deployment-review).
