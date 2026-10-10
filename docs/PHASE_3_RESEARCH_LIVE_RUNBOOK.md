# Phase 3: PostgreSQL acceptance and isolated Research demo preparation

Date: 2026-10-10. Starting HEAD: `5989af445ec80566580fc63c6e6795c2b1b8dcbe`, existing local `main`.

Phase 1 remains complete by the owner's current directive. Phase 2 remains complete for offline/local security acceptance: 454 distinct backend passes, 40 frontend passes, zero failures, and 35 PostgreSQL skips. Those counts are historical Phase 2 evidence, not new Phase 3 executions. See [Phase 2](PHASE_2_SECURITY_ACCEPTANCE.md) and [bounded demo readiness](RESEARCH_LIVE_DEMO_READINESS.md).

**Real-provider execution is NOT authorized.** No provider session, live Groq/Google request, environment-file change, production connection, backup edit, schema-code change, authorization change, push, deployment, branch or worktree is part of this phase. PostgreSQL fixture initialization/compatibility operations are confined to new disposable schemas; no existing database migration is permitted.

## PostgreSQL verification and approval

Read-only inspection confirmed Docker Engine 29.8.2, running `fm-tenant-postgres`, image `postgres:16-alpine`, server PostgreSQL 16.15. Container ID: `3d0127cbc8ad1b1841986fd95f804c3b7156d3e2e87e4f7805505292296b3243`. Both configured and effective published binding are exclusively `127.0.0.1:55432 -> 5432/tcp`.

Existing `fm_tenant_test` is owned by `fm_app`. Its only non-system schemas are `public` (owner `pg_database_owner`) and `langgraph_checkpoints` (owner `postgres`). Existing checkpoint data-table owner in the latter is `fm_checkpoint`, with ENABLE/FORCE RLS. Existing roles, memberships and grants are preservation targets, never setup identities. `fm_app` is a login; historical acceptance/checkpoint roles are NOLOGIN. There are 37 roles total, including built-in roles; only the built-in monitor memberships were observed.

| Existing schema | checkpoints | checkpoint_blobs | checkpoint_writes | checkpoint_migrations |
| --- | ---: | ---: | ---: | ---: |
| public | 13 | 18 | 44 | 10 |
| langgraph_checkpoints | 0 | 0 | 0 | 10 |

The owner explicitly approved one new disposable local database, one restricted temporary login, private temporary credentials, fixture schemas, and complete teardown during this session. This approval does not authorize provider execution or production access.

Shared fixture: `backend/tests/test_postgres_data_plane_integration.py::pg_repo`. It reads only `TENANT_TEST_DATABASE_URL`, validates a loopback PostgreSQL URL (rejecting host/service query overrides), rejects superuser/BYPASSRLS, creates a random `tenant_test_<uuid>` schema per case, sets `search_path=<schema>,pg_catalog`, initializes existing repository tables/policies, and drops exactly that schema in `finally`. It never needs checkpoint access or grants in `fm_tenant_test`.

The new database is owned by `postgres`, created from `template0`, and has PUBLIC database privileges revoked. The temporary identity has LOGIN, NOSUPERUSER, NOBYPASSRLS, NOINHERIT, NOCREATEDB, NOCREATEROLE, NOREPLICATION and connection limit 4; explicit database grants are CONNECT and CREATE on the disposable database only. No memberships or existing-object privileges are added. Cluster-wide PUBLIC rights on existing databases still exist; restricting the temporary role does not revoke those pre-existing grants. The test runner fixes the new database URL and only allows the local PostgreSQL network endpoint; it does not claim a new cluster-wide deny policy.

Exactly 35 cases were collected, including parameterized/imported cases:

| Module under backend/tests | Cases |
| --- | ---: |
| test_oauth_portability_postgres.py | 1 |
| test_product_invites_postgres.py | 12 |
| test_hr_reviews_postgres.py | 13 |
| test_agent_builder_postgres.py | 6 |
| test_research_postgres.py | 3 |

Compatibility checks already included in those 35 exercise invitation history, v12 HR tables/review preservation and v10 agent migration preservation in fixture-owned schemas. No broad migration/checkpoint suite is required or claimed. The Phase 2 socket-blocking runner is suitable for collection/offline tests only: it deliberately removes the PostgreSQL URL and must not be used to claim PostgreSQL execution.

Phase 3 PostgreSQL outcome: **35 passed, 0 failed, 0 skipped**, in 74.52 seconds; two existing dependency warnings described below. Disposable database/login `fm_phase3_7b063db0a8f8` was removed after tests. Teardown verified **0 roles, 0 databases, 0 sessions** matching that identity, and removal of its mode-0600 credential file and mode-0700 temporary directory. No new persistent PostgreSQL object remains.

The before/after snapshots are identical (both SHA-256 `e1d9037838923562a51bd972cd106713ec4e9c7d7c7f6807faca7febf155568f`): database ownership/ACLs, role flags/configuration, memberships, schema ownership/ACLs, relation ownership/ACLs/RLS flags, function grants, default grants, policies, and all eight checkpoint counts above. Container identity/image/state and both loopback binding records are unchanged. These are catalog/count preservation checks, not a row-by-row checkpoint payload audit; no payload was read. Original roles were never altered, and no test schema was created in the original database.

Execution used a temporary uncommitted wrapper: generated a private random password without output, passed administration SQL through standard input, fixed the disposable URL inside the test process, overrode provider/Google/checkpoint configuration, and rejected every network endpoint except `127.0.0.1:55432`. Only the five modules above ran. Provider outputs in custom-agent/Research tests were synthetic mocks, not real requests. The wrapper performed teardown in `finally`; no credential values or credential files enter this documentation or commit.

## Verified bounded protocol

| Item | Current code contract |
| --- | --- |
| Input | Synthetic B-direct v1 glossary: `RTO = recovery time objective`; no customer, HR, production or uploaded data |
| Benchmark digest | `2153e664f10f4cd0d412729ce842ab0165c8ed7b528500f2192c2f44d6ed379f` over the validated canonical benchmark |
| Modes / repetitions | Exactly ordered `[single, adaptive]`, one repetition, two atomically saved Tasks; no Fixed, rerun or resume |
| Requests | Maximum three actual HTTP transport invocations shared across both trials; a pre-send evidence failure can consume a slot without sending |
| Retries | Groq SDK `max_retries=0`, HTTPX transport `retries=0`; redirects and environment proxy discovery disabled |
| Model / output | `openai/gpt-oss-120b`; exactly 512 requested output tokens per call |
| Deadline | Shared 180-second monotonic deadline created before atomic admission, including queueing; never refreshed for the second trial |
| Body | Maximum 4096 actual serialized bytes per request; only accounted model/messages/max_tokens, plain system/user strings and exact approved HTTPS endpoint |
| Reservation | 3 × (4096 bytes + 256 estimated framing units) = 13,056 input accounting units; 3 × 512 = 1,536 requested output tokens; total 14,592 accounting units against 16,384 policy units |
| Usage | Provider-reported input/output usage retained separately; missing usage stops later requests; 16,384 reported tokens is a post-response stop threshold |

**Hard local request/deadline/serialization controls differ from estimated tokens and uncertain billing.** The 256-unit framing allowance is unvalidated. Serialized JSON bytes are not a provider tokenizer count. The 512 value is a requested provider cap, not independent proof of server compliance. Hidden framing, reasoning, failures, missing usage and remote cancellation can leave actual usage unknown or above the reservation. No hard total-token limit, spending cap, zero-cost claim or model-quality conclusion is established. Existing provider semantics in the readiness report were not revalidated against the external service in Phase 3.

Code inspected: `backend/run.py`, `app/experiments/demo_budget.py`, `app/api/routes/experiments.py`, `app/api/routes/tasks.py`, `app/agents/llm_client.py`, `app/core/config.py`, and `database/benchmarks/research-v1.json` (paths under `backend/`).

Only `backend/run.py` grants the demo runtime lease. It requires `single_process_local`, one replica, loopback HOST, DEBUG false and absolute-path local SQLite, and launches workers=1/reload=false. Generic Uvicorn/ASGI startup lacks authority. Known hosted markers and declarations above one worker are rejected. An exclusive POSIX advisory lock on the canonical SQLite sidecar excludes cooperating same-database processes. PID ownership rejects inherited authority; admission checks the repository database matches the lease. Topology is rechecked at transport, including after evidence persistence.

A read-only settings import from the normal backend working directory confirmed live/judge/demo/graph gates false, topology `unsupported`, replicas 0, no checkpoint URL, and model `openai/gpt-oss-120b`. Normal HOST `0.0.0.0` and DEBUG true are not the dedicated demo contract and would be rejected if demo authority were attempted. No settings, environment file or credentials were changed; the future isolated environment below is required.

A nonblocking admission mutex and consumed runtime lease permit one admission per process lifetime; failed admission writes consume authority. Lost/mismatched ledger, changed benchmark/model, exhausted reservation, oversized generated Report input or evidence persistence failure all fail closed. Cancellation and timeouts stop the shared ledger, preserve genuine partial evidence where writes succeed, and mark Tasks failed. Queued work cannot replenish authority. There is no dedicated Research cancellation HTTP endpoint. Graceful interruption should allow cleanup; hard termination can prevent terminal writes and cannot attest remote cancellation/zero billing. Restarting does not restore an admitted run and never authorizes another experiment. The lock is neither account-wide nor cross-host; do not unlink its sidecar while held.

Targeted Phase 3 offline verification: **6 passed, 0 failed, 0 skipped; 60 deselected**, using the existing network-blocking runner:

```sh
.venv/bin/python backend/tests/run_phase2_security_acceptance.py budget -q -ra -k 'launcher_preserves_disabled_behavior or database_lock_excludes_second_local_process or cancelled_admission_stops_already_queued_work or admission_reserves_all_future_input_and_output_before_execution or two_trials_three_actual_http_requests_shared_and_retained'
```

These cover both launcher branches, process/database exclusion, cancelled queued work, admission reservations, and the two-trial/three-request real-SDK MockTransport path. Two existing warnings: Starlette/AnyIO BlockingPortal deprecation and LangGraph allowed_objects pending default change. No live, native-browser or production evidence follows from these passes; the completed 66-case Phase 2 budget suite was not repeated.

## Future manual demo setup — separate approval required

Do not execute this section under Phase 3 authorization. The owner must separately approve local synthetic session/data setup and isolated credential handling, the exact one-experiment protocol, and token/billing uncertainty. The owner must ensure no other process/account user shares the key, no unrelated API execution, no restart/reload, and one host/database. Any hard spending-limit requirement is a NO-GO under current evidence.

1. Use a new private directory outside the checkout, mode 0700, with no `.env`; record its absolute path privately. Never copy an existing database, backup, environment file, auth cookie or production identity. Confirm chosen loopback port 8001 is free. Keep real hosted markers intact: if present, stop and investigate rather than deleting them to bypass admission.
2. Start from a clean environment with only required local PATH and the settings below. Import settings only after changing to that empty directory. Explicitly clear Google/OpenAI/Anthropic credentials and checkpoint settings. Keep live execution false during synthetic seed setup; no server or provider is needed to seed.
3. Through existing `Repository('sqlite:///<absolute-private-dir>/research.db')`, call `initialize()` to create this new disposable fixture database, then `save_user()` with a synthetic active user: id `USR-phase3-demo`, google_sub `synthetic-phase3-demo`, email `phase3-demo@example.invalid`, display_name `Synthetic Research Demo`, profile_picture null, email_verified true, created_at/last_login_at UTC ISO timestamps. Call `ensure_personal_workspace('USR-phase3-demo')` and keep its returned id privately. This uses existing local repository authority and does not add a login endpoint or weaken authorization.
4. Create one opaque local session with existing `create_opaque_token()`, `token_digest()` and `session_expiry()` from `app.security.session`; use `Repository.save_auth_session()` with a unique `SES-<uuid>` id, synthetic user_id, digest, created_at, expires_at and revoked_at null. Save the opaque token only in a mode-0600 curl config within the private directory, never stdout, shell history, command arguments, source or logs. Dispose the seed engine. This session is a local synthetic credential, not Google authentication evidence; its creation needs the separate approval above.
5. Read the owner-approved Groq key through a non-echoing prompt or approved private secret facility. Do not edit `.env` or reuse production credentials. Keep the key in the dedicated launcher process environment, never a command literal; child processes inherit environment secrets, so do not spawn unrelated tools. Use a wrapper to start the absolute repository `.venv/bin/python` with the absolute `backend/run.py`, working directory the private directory, and a minimal explicit environment. Do not run generic `uvicorn app.main:app`.

| Future dedicated launcher setting | Required value |
| --- | --- |
| DATABASE_URL | `sqlite:///<absolute-private-dir>/research.db` (four slashes before an absolute POSIX path) |
| HOST / PORT / DEBUG | `127.0.0.1` / `8001` / `false` |
| RESEARCH_LIVE_ENABLED / RESEARCH_DEMO_ENABLED | `true` / `true`, only after separate live authorization |
| RESEARCH_EVIDENCE_KIND | `provider_live` |
| RESEARCH_DEMO_TOPOLOGY / RESEARCH_DEMO_REPLICAS | `single_process_local` / `1` |
| WEB_CONCURRENCY / UVICORN_WORKERS | `1` / `1` |
| RESEARCH_JUDGE_ENABLED / LANGGRAPH_RUNTIME_ENABLED | `false` / `false` |
| CHECKPOINT_DATABASE_URL / GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET | empty |
| GROQ_MODEL | `openai/gpt-oss-120b` |
| GROQ_API_KEY | owner-approved isolated key, supplied privately |
| OPENAI_API_KEY / ANTHROPIC_API_KEY | empty |
| CORS_ORIGINS / FRONTEND_URL | `["http://127.0.0.1:5173"]` / `http://127.0.0.1:5173` |

Use no inherited configuration files or test fixture evidence mode. Do not launch the default frontend against another backend. A local Terminal HTTP client is sufficient and requires no Google request. Preserve any real hosted markers in the clean environment for rejection/investigation.

6. In the private curl config, set `header = "Cookie: app_session=<private opaque token>"`, `header = "X-Workspace-Id: <synthetic workspace id>"`, and `header = "X-Expected-User-Id: USR-phase3-demo"`. Set mode 0600, and never enable verbose/trace or print this file. Use `curl -q` so a user curlrc cannot inject retries/proxies; require `--noproxy '*'`, no redirects and `--retry 0`. Read-only preflight GET `/health`, `/api/v1/auth/me`, and `/api/v1/experiments/benchmarks` must confirm the dedicated service, synthetic identity and execution configuration; benchmark endpoint verified in `experiments.py`. Stop on mismatch.
7. Save this exact payload to a private file (it contains no credentials):

```json
{"benchmarkIds":["B-direct"],"modes":["single","adaptive"],"repetitions":1,"purpose":"One authorized synthetic bounded operational demo"}
```

Only after the separate approval and successful preflight, submit it once to `POST http://127.0.0.1:8001/api/v1/experiments/research`, with the private config, JSON Content-Type and file body. Do not retry even on a client timeout/unknown response: background execution may have begun. The backend 180-second provider deadline differs from a Terminal HTTP client's timeout. Never invoke rerun, evaluation, ordinary tasks or a second experiment with these credentials.
8. Obtain the experiment/Task IDs from the response or authenticated read-only list. GET `/api/v1/experiments/research/<experimentId>` and `/report`, and inspect both Tasks' persisted admission/attempt/usage/terminal events. Preserve genuine partial/failed evidence, exact invocation counts and unknown usage. Export to the private directory without cookies/keys, keep separate from historical fixture samples; inspect/redact before sharing. No significance, winner, production-readiness or fabricated usage claim from two trials. Provider account telemetry access needs its own authorization.

## Teardown and evidence preservation

PostgreSQL: first disable the exact temporary role with NOLOGIN; terminate only sessions matching that role/new database; drop only that disposable database, then that role. Remove the private credential file/directory even after test failure. Verify zero matching roles/databases/sessions. Compare original database/role/membership/schema/relation/function/default-grant/policy fingerprints and all eight checkpoint counts. Recheck container ID and configured/effective binding. No modifying `fm_tenant_test`, its ACLs or checkpoint tables to make cleanup pass.

Future demo: stop the exact dedicated backend PID gracefully and verify port 8001 and its process are gone. Before removing credentials, preserve a sanitized report and both trial records under an approved evidence-retention decision. While the isolated database remains, revoke the synthetic session using existing repository revocation, then dispose its engine. Remove the private curl config and provider key from wrapper memory/environment; revoke/delete any temporary provider key through its owner-approved credential workflow (do not silently alter shared keys). Remove the disposable SQLite database/WAL/SHM and lock sidecar only after no process holds it; never purge historical/production evidence. Confirm the private directory/credential files are gone and default execution gates remain disabled without editing any `.env`. On forced termination, explicitly report incomplete terminal evidence and uncertain remote usage.

## Safe next Terminal commands and checkpoint

These commands perform read-only verification, not setup or live execution:

```sh
cd /Users/shreetej/Downloads/FMProject
git rev-parse HEAD
git status --short
git diff --check
shasum -a 256 AGENTS.md
docker inspect fm-tenant-postgres --format '{{.Id}} {{.Config.Image}} {{.State.Status}} {{json .HostConfig.PortBindings}} {{json .NetworkSettings.Ports}}'
cat docs/PHASE_3_RESEARCH_LIVE_RUNBOOK.md
```

Expected AGENTS checksum remains `a5f46def185ce9e844d9d468912f3fbee4dbf2d8f14f08c91c02553352e87efd`; it stays untouched and untracked. At most one documentation-only local commit, containing this runbook and the tracker, is authorized. Its actual hash is obtained after committing; no document can embed its own hash.

Next checkpoint: owner reviews Phase 3 evidence and decides whether to authorize exactly one isolated real-provider operational demo with explicit estimated-budget uncertainty. No live-provider authorization is implied by local PostgreSQL acceptance. Existing deployed OAuth/WebSocket, retention-policy and provider-certified budgeting gates remain open. Phase 4 directive and authorization must be supplied separately. **STOP before provider session creation, production changes or Phase 4.**
