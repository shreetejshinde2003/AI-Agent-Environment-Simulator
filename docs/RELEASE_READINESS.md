# Phase 10 security audit and release-readiness assessment

## Local OAuth correction; production release remains paused

See [OAuth portability evidence and acceptance](OAUTH_PORTABILITY.md). Schema 14
now also creates a digest-only pre-authentication transaction table/index. Verify
its production CREATE/DML privileges and restricted PostgreSQL acceptance before
release. Multi-device production sign-in is not yet accepted. The Railway hold,
database binding, role/ownership/RLS, backup/restore and old-backend maintenance
blockers remain open. No settings, push, migration or deployment was authorized.

Verified locally on 7 October 2026. This is a repository/code/test assessment,
not production acceptance or an external penetration-test certification.
The final [acceptance report](PHASE10_ACCEPTANCE_REPORT.md) supplies exact results.
No production connection, credential, migration, deployment or flag was changed.

## Current local product correction — 2026-10-08

The post-deployment correction uses schema 14 and explicitly changes executed-run retention to owner-authorized permanent purge. Invitations are now one-time and managed through persistent masked history; custom agents archive through immutable revisions. Member transitions serialize and protect the last active owner. Research definitions ship with the backend; readiness separates REST/workspace availability from live events.

[Current correction acceptance](POST_DEPLOYMENT_PRODUCT_CORRECTIONS.md) supersedes earlier retention/invite behavior and validation totals. The Phase 10 audit below remains historical evidence. No production migration or settings changed. Release must separately review schema 14, backups, the optional same-database checkpoint bridge and its NOLOGIN restricted role, and the unresolved production WebSocket authentication topology. Graph purge fails closed until atomic cleanup is available.

## Independent audit scope and security evidence

The audit inspected authentication, tenant transactions/RLS inventory, IAM and HR
permission resolution, API admission/reads/writes, worker authorization, HR source
binding, immutable reviews, checkpoint role validation/serializer, WebSocket
admission/delivery, frontend workspace state and research comparisons/provenance.
Historical completion reports were reconciled with current files and rerun tests.

| Boundary | Current protection | Re-executed regression evidence |
| --- | --- | --- |
| Session/OIDC | Opaque digest, expiry/revocation/active-user checks; state/nonce/PKCE; verified Google token claims; safe errors. | `test_google_auth_api.py`, `test_auth_storage.py`, `test_browser_session_security.py` |
| Workspace/organization | Server-derived identity and active membership; personal owner-only; unknown roles fail closed. | `test_workspace_resolution.py`, `test_rbac_adversarial.py`, `test_rbac_api_enforcement.py`, `test_organization_member_management_api.py` |
| Owner/Admin/Member | Central permission map; Admin cannot manage Admin/Owner authority; owner-only eligible purge. | `test_membership_role_management.py`, `test_rbac_policy.py`, `test_recycle_bin.py` |
| HR role separation | Explicit active Recruiter/Reviewer/Approver assignments; Personal/IAM-only exclusion; immediate revocation. | `test_hr_human_role_adversarial.py`, `test_hr_role_tenant_wiring.py`, `test_postgres_hr_roles.py` |
| Custom-agent ownership | Tenant/manager checks, immutable config revisions, revision-pinned member runs, no arbitrary tools/provider URLs. | `test_agent_builder.py`, `test_agent_builder_postgres.py` |
| HR sources and proposal acceptance | Exact tenant/revision ownership, bounded schema validation, three authorization gates, discard revoked output. | `test_hiring.py`, `test_hr_agents.py`, `test_hr_agents_postgres.py` |
| HITL actor/stale conflicts | Authenticated actor, locked revision/state transitions, optimistic version, immutable submissions/events, no approval transfer. | `test_hr_review_storage.py`, `test_hr_reviews_api.py`, `test_hr_reviews_postgres.py`, `test_hr_workflow_postgres.py` |
| Simulation/upload/recycle | Tenant ownership, generic HR exclusion, bounded unexecuted input, evidence-preserving deletion semantics. | `test_simulation_workspace_api.py`, `test_upload_tenant_api.py`, `test_recycle_bin_postgres.py`, `test_hr_agents.py` |
| Research ownership/integrity | Scoped list/detail/export/rerun/scoring; immutable trial config, append-only output-bound rubric; source fingerprint validation. | `test_research.py`, `test_research_postgres.py`, `test_final_persistence.py` |
| Events/WebSocket | Exact browser-origin gate; authenticated workspace; recheck every delivery and at most 30 seconds idle; REST reconnect recovery. | `test_websocket_workspace_isolation.py`, `test_browser_session_security.py` |
| Checkpoints/resume | Internally derived thread, restricted dedicated login/schema, thread FORCE RLS, live authorization, data-only serializer, same-task lock. | `test_checkpointing.py`, `test_postgres_checkpoint_runtime.py`, `test_postgres_graph_acceptance.py`, `test_checkpoint_postgres_sql.py` |
| Missing context/actor spoofing | Transaction-local trusted context; no client actor authority; FORCE RLS/direct SQL checks and immutable guards. | `test_tenant_db_context.py`, `test_postgres_data_plane_integration.py`, `test_hiring_postgres.py`, `test_hr_reviews_postgres.py` |
| Frontend private-data exposure | Scoped HR/Research/Builder mounts; read cancellation; simulation generation fences, immediate stale-data masking and foreign acknowledgement denial. | `simulationData.test.js`, `hr-workflow.test.js`, `research.test.js`, final real-browser checklist |

No RLS weakening, BYPASSRLS grant, hidden failure suppression or new autonomous HR
operation was used. The confirmed frontend privacy race, SQLite migration guard,
and research integrity gaps are corrected and recorded in the acceptance report.

## RLS inventory and trust assumptions

All 22 current application tenant tables have ENABLE + FORCE RLS:

- Roots/bootstrap: `workspaces`, `organization_memberships`.
- HR authority: `organization_human_role_assignments`.
- Execution: `simulations`, `tasks`, `agent_executions`, `agent_messages`,
  `activity_events`, `run_events`, `simulation_metrics`, `simulation_uploads`.
- Prepared uploads: `uploads`.
- Custom agents: `custom_agents`, `custom_agent_revisions`.
- HR records: `hr_requirements`, `hr_requirements_revisions`, `hr_role_knowledge`,
  `hr_role_knowledge_revisions`, `hr_job_descriptions`, `hr_job_descriptions_revisions`.
- Human decisions: `hr_review_submissions`, `hr_review_events`.

No classified tenant table is deferred. `users`/`auth_sessions` are identity data;
`schema_version`, `dataset_registry`, and `agent_roster` are system-global. Their
trusted-service access is deliberate and is not claimed to be tenant FORCE RLS.
Three checkpoint data tables separately enforce exact thread equality; migration
metadata belongs only to the migration owner. Checkpoint runtime has no application
schema access, owner membership or schema CREATE.

RLS trusts API/worker authentication and installed transaction context. A stolen
trusted-service credential/arbitrary SQL could select another tenant context;
GUCs are not cryptographic identity proofs. SQLite enforces application permissions,
not row-level database policies. Organization membership intentionally shares
simulation evidence across eligible active members, rather than per-creator secrecy.
HR output remains available only to authorized HR humans. Source text is untrusted;
prompt restrictions and strict output schema are not proof of model factual correctness.
The documented workflow allows combined HR roles; independent actors were used in
the demo but organizational separation of duties is not universally mandatory.

## Migration and persistence audit

Schema remains **13**; no Phase 10 migration/table/version increase was needed.
Clean/current SQLite initialization, historical V1 backup/archive conversion,
V5/V6 membership evolution and representative V9/V10/V11/V12 additive compatibility
are covered by the retained suite. New tests exercise completed V1 archives while
upgrading operational version markers 2/9/12, and preserve interruption denial at
version 1. These are controlled migration fixtures, not every possible historical
production database shape.

Real PostgreSQL tests create random isolated schemas under a non-bypass role,
verify fresh initialization/reinitialization, recreate representative older table
inventories and run additive migrations while retaining execution/custom/HR/review
history. The consolidated SQLite/PostgreSQL test combines approved stale HR history,
new JD revisions, custom config, six research trials and recycled/restored execution
across repeat initialization. Real saver tests reconnect, roll back context errors,
crash a worker and resume Single/Fixed/Adaptive without repeating committed stages.
Existing checkpoint serializer/schema tables remain compatible with pinned libraries.

The root local database remains at version 13 with no business records; the old
`backend/simulator.db` is version 9 with its existing execution records and was not
migrated. A cleanup byte-fingerprint assertion detected root SQLite header changes
from four existing authentication-denial tests that started the default repository.
A copy-only reproduction changed offsets 27/95 while its logical dump remained
identical. Those four tests now explicitly isolate startup and assert the default
file fingerprint is unchanged; targeted acceptance verifies zero changed bytes.
The initial combined comparison snapshot was removed prematurely by the temporary
cleanup helper, so byte-for-byte preservation of every original file/checkpoint
table is not claimed. Existing credentials/AGENTS.md/backend database modification
times predate this task; local database integrity checks pass. Startup from
`backend/` would select its relative database unless `DATABASE_URL` is explicit.
Production migration must use a backed-up isolated copy with its real inventory,
ownership, retained evidence and policies before applying changes to a live service.

## Production gates — unverified and not authorized in Phase 10

| Gate | Observed state / required verification | Acceptance scope |
| --- | --- | --- |
| Frontend proxy/session topology | Local correction generalizes `/api/v1/*` to Railway and makes all production REST same-origin; `/health` has its own rewrite and SPA fallback excludes API paths. Cookie attributes are unchanged. Verify fresh OAuth callback/session, workspace/HR/research and run admission through deployed rewrites. | Local production-build fixture passed; deployment and real OAuth remain pending and require approval. |
| OAuth/domain/branding | Verify actual client/audience/redirect/front-end/trusted origins, HTTPS cookie attributes and browser cross-site behavior, consent-screen support/privacy/branding and account restrictions in the intended deployment. | Local tests mock Google; real fresh sign-in remains unverified. |
| PostgreSQL migration/runtime role | Back up and rehearse actual deployed schema/data migrations; verify NOSUPERUSER/NOBYPASSRLS, effective memberships, 22 ENABLE/FORCE policies, least privilege and tenant-context rollback. Current initializer requires schema/migration privileges; its separation from long-lived service privileges needs an operator-reviewed plan. | Local isolated acceptance only. |
| Checkpoint roles and activation | Provision separate permanent migration owner and non-bypass runtime login, install/review exact policies, verify no CREATE/migration/application privileges and current serializer compatibility. Keep `LANGGRAPH_RUNTIME_ENABLED=false` until deployed checks pass. | No production graph activation. |
| Worker/restart/recovery | Run one API worker; verify startup interruption handling, restart, explicit graph resume where enabled, advisory-lock exclusion and final evidence parity in that environment. Coordinated multi-worker startup and a durable queue are absent. | Real local process crash/recovery passes; deployment behavior unverified. |
| WebSocket/reconnect | Direct Railway WSS cannot receive the host-only session cookie established through Vercel. Existing backend requires that cookie, trusted origin and workspace authorization. Approve a compatible transport/domain design before claiming production live events. | No new token protocol or WebSocket proxy. REST polling passes locally with live events offline; production WebSocket auth remains blocked by topology. |
| Groq provider acceptance | Separately approve a small bounded live run set for model availability, failure handling, usage return and HR JSON validity. Repeated comparative research additionally needs a predeclared design and independent human assessment. | No paid/live request made; not needed for LOCAL acceptance. |
| Research runtime/judge gates | Keep `RESEARCH_LIVE_ENABLED` and `RESEARCH_JUDGE_ENABLED` at their reviewed defaults until explicitly approved. Retain original fixture kind and implementation/benchmark snapshots. | Fixture machinery passes; live quality/speed/cost/significance unknown. |
| Reproducible packaging | `groq` and `httpx` requirements remain unpinned. Capture and approve a resolved production dependency set, smoke-test it and retain source/config versions. Current installed package inventory is in final evidence. | No dependency replacement or reinstall. |
| Operations and evidence retention | Establish backup/restore, error monitoring, resource/provider admission quotas and retention/account-erasure policy. Automatic retention/account erasure and a durable job queue are absent. Verify privately provisioned domain datasets if needed. | No production operational readiness claim. |
| License/data permissions | Repository license selection remains pending; use only authorized synthetic/domain material. | Academic demo can use synthetic fixtures. |

These gates are material limits, not permission to change deployment configuration.
No live provider test is necessary for final local acceptance. A later request must
identify provider, bounded request count, purpose and token/cost exposure before it
runs. Google OIDC verification and Groq AI verification are distinct gates.
The final verdict can be locally complete while these production gates remain.

## Local routing correction — deployment review

Local change only, 2026-10-08, on `main` from
`16173864f0c32533b8e6b87e5e151c9adee1a791`. Nothing pushed or deployed.
All production JSON browser REST clients use relative `/api/v1/...` with
credentials included; local development continues to use a configured backend
or localhost:8000. Public health uses same-origin `/health` forwarding. Rewrites
use the existing public Railway destination, followed by a SPA rule excluding API
paths, using [Vercel's documented external rewrite syntax](https://vercel.com/docs/routing/rewrites).
The local evaluator validates the checked-in patterns; it is not the Vercel platform.

Production steps that require separate approval:

1. Push this local commit and deploy the frontend with `frontend/vercel.json` at
   the configured Vercel project root. Verify generalized rewrite ordering, no
   inappropriate authenticated-response caching, unknown API JSON/404 behavior,
   frontend deep links and public health forwarding in the deployed environment.
2. Review Vercel build variables: **no `VITE_*` variable is required for production
   REST**. `VITE_API_BASE_URL` is ignored for production REST and is only useful
   in development or as the existing WebSocket-origin fallback. `VITE_WS_URL`
   remains the explicit production live-event endpoint setting; removing
   `VITE_API_BASE_URL` requires retaining/reviewing `VITE_WS_URL`. A WSS URL alone
   does not solve authentication. No new rewrite variable or secret was added.
3. Review Railway `GOOGLE_REDIRECT_URI`, `FRONTEND_URL`, and the Google OAuth
   authorized redirect registration. The callback must go through the frontend
   `/api/v1/auth/google/callback` origin to establish the same host-only session
   as REST. Review any existing registration before making separately approved
   changes. No OAuth credentials or settings changed locally.
4. Keep/review the frontend origin in Railway `CORS_ORIGINS`. Same-origin browser
   REST no longer depends on browser cross-origin CORS, but the backend also uses
   this allowlist for mutation/CSRF and WebSocket trusted-origin checks.
5. Validate fresh sign-in → `/auth/me` → workspace discovery/selection → history
   → run admission → logout through Vercel with existing secure/HttpOnly/SameSite
   semantics. REST cookie topology is coherent in the code contract, contingent
   on callback routing and deployed Set-Cookie forwarding. No production database
   change is needed for this frontend correction.
6. Separately approve/design a WebSocket transport that can use existing cookie
   authentication; direct Railway WSS is incompatible with a Vercel host-only
   cookie. Do not claim production live events until deployed session, revocation,
   workspace and reconnect checks pass. No Vercel WebSocket proxy or new token
   semantics were assumed. Paid/live-provider checks still need separate approval.

Final validation: frontend **184 passed, 0 failed/skipped**; focused routing tests
**24 passed**; affected backend **35 passed, 0 failed/skipped, 2 dependency warnings**.
Lint passed (2 existing Fast Refresh warnings); build passed (one >500 kB chunk
warning); whitespace validation passed. No Python implementation changes or
PostgreSQL acceptance reruns. Backend scope: `test_google_auth_api.py`,
`test_browser_session_security.py`, `test_websocket_workspace_isolation.py`,
`test_simulation_workspace_api.py`. Initial mistyped test filenames collected no
tests; the corrected invocation produced the reported 35 passing tests.

Browser evidence and detailed observed journey are in [Project state](PROJECT_STATE.md#local-production-rest-routing-correction--2026-10-08).
Provider output is synthetic; auth APIs, admission and persistence are real local
fixture operations. No production service/account/database/provider was touched.

Reproduce locally from the repository root:

```sh
.venv/bin/python backend/tests/ux_output_browser_fixture.py
# In a second terminal:
cd frontend
npm run build
node tests/fixtures/productionProxy.js
```

Visit `http://127.0.0.1:5179/_local_browser_fixture/recruiter`, select the seeded
organization, inspect history and admit a Single run with
`What is 6 times 7? Give only the final number.`. The SDK mock returns `42`.
The proxy binds only localhost:5179 and forwards only to localhost:8019, replacing
the checked-in public rewrite destination for acceptance. It serves the production
build and intentionally does not proxy WebSockets. To reproduce controlled HTML
failure, restart the proxy with `FM_FIXTURE_WORKSPACE_HTML=1`, then reload the
browser. Stop both processes afterward; the fixture removes its temporary database.
