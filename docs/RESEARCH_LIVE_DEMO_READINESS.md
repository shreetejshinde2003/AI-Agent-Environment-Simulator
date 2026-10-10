# Bounded Research live-demo readiness

Updated 2026-10-10. Implementation baseline: local `main` at `67f699d18e6415b88eefbf73b6f3d5538072f4ab`.

**Live execution remains NO-GO.** The local implementation now bounds HTTP transport attempts and admission, but does not prove a hard experiment-wide model-token or billing ceiling. No provider, credential, gate, deployment or production change was made. Execution defaults remain disabled.

## Verified policy

The existing authenticated Research Lab admission/execution path applies `bounded-demo-v1` whenever evidence kind is `provider_live`. `RESEARCH_DEMO_ENABLED` defaults false and lets isolated deterministic-fixture tests exercise the same policy. Ordinary simulations retain their existing provider behavior. Broader historical fixture research protocols remain supported for mocked acceptance; fixture configuration is not authorization for real calls.

| Control | Enforced behavior |
| --- | --- |
| Admission | Exactly B-direct v1, modes ordered `[single, adaptive]`, repetitions 1, exactly two Tasks in the existing atomic repository admission. Approved benchmark snapshot SHA-256: `2153e664f10f4cd0d412729ce842ab0165c8ed7b528500f2192c2f44d6ed379f`. Changed sources/checks/directive are rejected. |
| Scope | One admission per process lifetime, including after failure. No rerun, Fixed, extra case, repetition, judge or durable graph runtime. Single executes Direct; Adaptive executes Research → Report through the established engine. |
| Attempts | Shared maximum **3 transport reservations**, immediately before the underlying HTTP transport invocation. Every specialist call consumes the same ledger. A reservation cannot be refunded. Pre-send persistence failure can consume a slot without any network invocation; evidence distinguishes reservations from `transportInvocations`. |
| Retries | Dedicated Groq client sets `max_retries=0`; underlying HTTPX transport sets `retries=0`. Redirect following and environment proxy discovery are disabled for this client. Only POST to Groq's chat-completions endpoint is admitted. |
| Output | Every request must carry **512 max output tokens**. Streaming/tools are rejected. A provider report exceeding that cap fails the stage and prevents further requests. This validates request settings and reported usage, not independent provider compliance. |
| Request reservation | Serialized JSON body ≤ **4096 bytes**. Each attempt permanently reserves body bytes + 512 units against a shared **16384-unit** policy. With three attempts the maximum reservation is **13824 units**. These mixed units are explicitly labelled; they are **not a verified total-token bound**. Oversized requests fail before transport. |
| Observed usage | Aggregate provider-reported prompt + completion tokens across successful responses; stop if reported cumulative usage exceeds **16384 tokens**. This is a post-response check, not a hard preflight ceiling. Missing usage retains unknown coverage and reservations, accepts only the genuine returned output, then stops subsequent calls. Failed/timeout/cancelled requests have unknown usage. No zero-cost claim. |
| Deadline | Shared **180-second monotonic deadline**, starting at ledger creation immediately after atomic admission. Includes queuing and all trial work. Rechecked at stage/provider admission and immediately before transport; asynchronous timeout covers the stage, SDK request and response-body read. Expired responses fail closed. No fresh deadline on later stages. |
| Failure | HTTP error, transport failure, deadline, cancellation, invalid request, exhausted budget, missing ledger or mismatched tenant/user/run scope prevents subsequent calls. Persist before sending; no call if that write fails. Gate/configuration and existing tenant permission are rechecked on the reservation write. |
| Evidence | Existing tenant-owned Task JSON and RunEvents retain `demoPolicy`, retry policy, reservation/transport counts, reported usage coverage, stop reason, stage results and explicit trial completion/failure. Cancellation is a stop reason; authoritative Task status remains failed. Completed earlier trial/stage output survives; failed output is not invented. Reports retain these events. |
| Restart | Ledger authority is intentionally process-local. Missing state fails closed; saved events cannot replenish or reconstruct the budget. No demo resume. No schema/table/migration added; new optional JSON fields preserve schema-14 and historical Task loading. |

The three-request ceiling covers invocation of a zero-retry HTTP transport, including connection failures conservatively. It cannot count provider-side internal computation or prove whether a failed connection reached the server. Cancellation/timeout closes local admission; it cannot recall a request already accepted remotely. Persistence can itself fail, so explicit terminal evidence is guaranteed only while the authorized evidence store remains writable; the pre-send reservation remains the durable conservative bound.

## Mock-only acceptance

**167 passed, 0 failed, 0 skipped**, two existing Starlette/AnyIO and LangGraph dependency warnings. Selection:

```text
.venv/bin/python -m pytest \
  backend/tests/test_research_demo_budget.py \
  backend/tests/test_research.py backend/tests/test_research_contracts.py \
  backend/tests/test_llm_client.py backend/tests/test_task_pipeline.py \
  backend/tests/test_single_graph.py backend/tests/test_adaptive_graph.py \
  backend/tests/test_fixed_graph.py backend/tests/test_graph_runtime.py \
  backend/tests/test_quality_evaluation_api.py \
  backend/tests/test_tenant_execution_wiring.py -q
```

The new 33-case budget suite uses the installed **Groq 1.7.0 / HTTPX 0.28.1 SDK**, an in-memory HTTP transport, synthetic test-only key and isolated SQLite data. No external provider request is sent. It verifies:

- two persisted admissions and three actual MockTransport requests shared across Direct/Research/Report; real SDK factory receives zero retries and the underlying transport factory receives zero retries;
- an intentionally retry-enabled SDK cannot send a fourth request through the budget transport;
- 429/500 cause exactly one transport request and no SDK retry or later specialist call;
- protocol/benchmark changes, repeated admission, missing/mismatched ledger, expired deadline, oversized body, output setting, exhausted reservations and failed pre-send evidence writes send no further request;
- in-flight monotonic timeout, cancellation and connection failure retain partial evidence; cancellation during Adaptive preserves the completed Single output and leaves Report unstarted;
- missing usage remains unknown and stops later calls; reported overage fails closed without inventing output;
- gate/judge/unauthenticated/cross-tenant rejection and blocked model evaluation, plus unchanged historical sample bytes/checksum.

The remaining tests verify the existing research protocols, authorization/revocation and tenant execution wiring, ordinary Single/Fixed/Adaptive/pipeline behavior and evaluation/provider contracts. The initial deadline test exposed cancellation misclassification; the correction uses monotonic expiry to classify deadline cancellation correctly. Final acceptance is the count above.

No frontend code changed; no frontend checks required. No fresh PostgreSQL/RLS, browser, production or real-provider acceptance is claimed. Historical 47-test readiness acceptance and 42-trial sample are prior fixture evidence, not new live results. Historical report/manifest files were not modified.

## Remaining NO-GO conditions and real-test authorization

1. **Hard token ceiling is unproven.** Bytes + output-cap reservations are an enforceable local admission policy, not model-token accounting. Verify the selected model's tokenizer/chat-template overhead, reasoning-token accounting and server output-cap semantics, then implement/test a conservative pre-send total-token bound if a hard token ceiling remains required. A successful provider response can disclose a total over the post-response threshold; errors may never disclose usage. Do not present 16384 units as 16384 guaranteed tokens.
2. **The latch is process-local.** It does not coordinate multiple workers/hosts or forbid a new experiment after process restart. The supported prospective environment is exactly one dedicated backend process, one event loop, one isolated local database, no reload/restart during the admission, no unrelated simulation/HR/agent execution, and no second server sharing credentials. Distributed/restart-safe authorization would need a separately reviewed durable design. Lost-state execution fails closed rather than resuming.
3. **Remote completion and billing remain external.** Timeout/cancellation can leave remote work running. Provider account telemetry is separate from returned stage usage; missing usage stays unknown. Account-wide traffic is outside this experiment's bound.
4. **No approval has been granted.** After resolving the hard-token condition, obtain explicit authorization naming the dedicated loopback environment/database, local credential handling, provider/model, approved benchmark digest, one two-trial experiment, three HTTP attempts maximum, 512 output cap, validated total-token limit and 180-second deadline. Judges, reruns, durable resume, auxiliary agents, other traffic and deployment must be excluded. Model availability and current provider semantics also require verification before that authorized test.
5. **Review retained evidence and disable afterwards.** Use normal authenticated Research Lab endpoints and tenant permissions. Retain/export exact Task IDs, raw outputs, stages/routes, budget events, provider usage and failures; keep the genuine report separate from the historical sample. Stop the dedicated process after the authorized experiment and restart only with gates disabled. Do not purge evidence.

Approval of this implementation does not enable a provider call. Stay stopped before any credential setup, live request, push or deployment.
