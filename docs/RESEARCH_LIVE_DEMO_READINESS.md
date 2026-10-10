# Bounded Research live-demo readiness

Updated 2026-10-10, from local `main` baseline `bf3fdcd347b159da7b2e4bc269ee03ae9d6804c7`.

**Hard-token guarantees remain NO-GO.** A small real-provider test is conditionally suitable only if the owner explicitly accepts an estimated total budget and the local deployment conditions below. No such test is authorized or executed here. All effective execution gates remain disabled; no credential setup, production connection, migration, push or deployment occurred.

## Exact inspected model and request path

Effective Direct, Research and Report model: **`openai/gpt-oss-120b`**. The configured fast model is `openai/gpt-oss-20b`, but none of these three agents selects it. Admission and the provider path now reject a different demo model. Each agent uses the existing `call_llm` adapter; all three demo requests pass through the same budget transport. Report includes generated Research text, so its complete prompt cannot be known at admission.

Installed versions: **Groq 1.7.0, HTTPX 0.28.1**. The SDK strips omitted arguments and serializes a compact UTF-8 JSON body through `groq._utils._json.openapi_dumps`: `ensure_ascii=False`, separators `(',', ':')`, `allow_nan=False`. The exact admitted body keys are `model`, `messages`, `max_tokens`; actual messages are system and user strings. There are no implicit client-added documents, tools, judges or additional message bodies. Transport rejects unaccounted body fields, models, roles, non-string contents, non-HTTPS/alternate endpoints and query parameters. It measures the SDK's final bytes, not a separately reconstructed approximation. Generated upstream text and non-ASCII characters are subject to the same final-byte check.

Groq documents `max_tokens` as deprecated in favor of `max_completion_tokens`, with the same generated-completion limit; this patch retains the established **512** setting and rejects conflicting extra fields. Reasoning effort is omitted, so GPT-OSS uses the documented provider default **medium**. A short completion allowance may leave no usable final answer after reasoning; existing empty-output failure remains honest. These are provider API semantics, not independent server-compliance proof. Sources inspected October 10: [Groq API reference](https://console.groq.com/docs/api-reference), [reasoning documentation](https://console.groq.com/docs/reasoning).

## Tokenizer finding

A model-specific public tokenizer/renderer exists: [OpenAI Harmony](https://github.com/openai/harmony) exposes `HARMONY_GPT_OSS` and completion rendering; the [official GPT-OSS model repository](https://huggingface.co/openai/gpt-oss-120b/blob/34a49b3f83ac94f307cfaeb145c90a134787e8ee/chat_template.jinja) supplies a chat template. That template has model identity, date/cutoff, reasoning-effort and built-in-tool rendering inputs as well as message contents.

No `tiktoken`, `transformers`, `tokenizers` or `openai-harmony` package is installed in this backend environment. No package/model/tokenizer was downloaded. **Inference from the inspected public material:** a pinned local reference tokenizer could count a chosen reference rendering for all three paths, including Report just before transmission, but exact Groq template/version/injected-prefix parity has not been established. Counting message content alone omits framing; tokenizing the HTTP JSON counts a different representation. Neither is an exact server prompt count. The Groq API/SDK material inspected does not supply a provider-certified preflight count for this path. Installing a tokenizer would not resolve that parity gap by itself.

Consequently, this implementation intentionally uses an explicit conservative engineering estimate. The **256-unit framing margin is unvalidated**, not a proof about Groq's template. Hidden/server-injected input, reasoning accounting, model aliases and usage on failed/remote-cancelled requests remain external assumptions. No hard experiment-wide total-token or billing upper bound is claimed.

## Enforced limits and reservations

| Control | Verified local guarantee |
| --- | --- |
| Protocol | Exactly the approved B-direct v1 digest `2153e664f10f4cd0d412729ce842ab0165c8ed7b528500f2192c2f44d6ed379f`, modes `[single, adaptive]`, one repetition, two atomically saved Tasks. No Fixed, rerun, judge or durable graph runtime. |
| Admission authority | Nonblocking process mutex protects admission, including overlapping requests. One admission per launcher/process lifetime; a failed admission write consumes authority. No new admission while queueing or after ledger loss/failure. |
| Admission input reservation | Permanently hold **3 × (4096 serialized bytes + 256 estimated framing units) = 13056 input estimate units**, before saving either trial. This includes capacity for unknown future Report text. |
| Admission output reservation | Hold **3 × 512 = 1536 requested output tokens**. This is the sum of requested provider caps, not locally enforceable generated-token proof. |
| Combined reservation | **14592 estimated units** held against **16384-unit** admission policy. If capacity is insufficient, persist zero trials and send zero requests. Both Tasks carry an existing `demo_budget_admitted` event with reservations and `hardTotalTokenGuarantee=false`. No refund for short responses, HTTP errors, timeout, cancellation or missing usage. |
| Per-request preflight | Exact serialized body ≤ **4096 bytes**; output setting **512**; only the inspected model and accounted plain-text request shape. Each transport slot consumes body bytes + 256 margin + 512 against the already admitted capacity. Oversized generated predecessor text prevents the Report request; retained Research output survives. |
| Attempts and retries | Shared maximum **3 actual zero-retry HTTP transport invocations**. SDK `max_retries=0`, HTTPX `retries=0`, redirects off, environment proxy discovery off. Reservation/evidence write precedes invocation; failed writes can consume a slot without sending. No application/specialist call bypasses the transport ledger. |
| Usage | Retain provider-reported input/completion sums separately and together, plus unknown/partial coverage. The existing **16384 reported-token post-response threshold** stops further calls if exceeded. It cannot prevent that response from already consuming more than the estimate/threshold. Missing usage stops later calls and retains unknown coverage; genuine available output may be retained. No cost or zero-usage invention. |
| Deadline | Shared **180-second monotonic deadline**, now created before atomic admission. Includes admission, queueing and execution; no refresh for the second trial. No new provider call after expiry. Stage/SDK/response-body timeouts and expired responses fail closed. |
| Evidence | Existing Task/stage/events retain admission reservations, consumed estimated units, transport slots/invocations, observed usage, stop reason, partial outputs and explicit trial completion/failure. Cancellation remains a stop reason with authoritative failed Task status. Evidence-store failure can prevent later terminal writes; it does not permit an unreserved call. |

## Deployment admission verification

Defaults are `RESEARCH_DEMO_TOPOLOGY=unsupported`, `RESEARCH_DEMO_REPLICAS=0`, with live/judge/demo-fixture/graph gates false. Generic ASGI/Uvicorn entrypoints have no launcher lease and reject demo admission even if the live gate is mistakenly set. They cannot infer a supported topology simply from missing environment variables.

Only the normal local `backend/run.py` demo branch can grant runtime authority. It requires explicit `single_process_local`, replicas exactly 1, configured loopback HOST (`127.0.0.1` or `::1`), DEBUG false and an absolute local SQLite database path. It calls Uvicorn with **workers=1, reload=false**. Worker-count declarations above one and known Railway/Kubernetes/Vercel hosted markers are rejected. An exclusive advisory lock on the canonical database sidecar excludes another cooperating process on the same host/database; PID ownership rejects inherited fork authority. Admission also verifies that the authoritative repository matches the launcher's database. Topology/lease is rechecked at the transport boundary, including after the pre-send evidence write. The disabled/non-demo launcher behavior is preserved.

**Scope limitations:** this is a POSIX local launcher contract, not remote-host attestation or an account-wide lock. Separate hosts/databases or uncooperative programs using the same credentials cannot be discovered or bounded. The owner must ensure one dedicated process, one database, no other credential users, no reload/restart and no unrelated application traffic. Declared multi-worker/multi-replica/hosted or unknown topology fails closed; arbitrary concealed replication is not a supported guarantee. Restart does not reconstruct budget authority for saved runs; fresh authority after restarting must never be treated as authorization for another experiment. Do not unlink the advisory-lock sidecar while a process holds it.

No schema, migration, permission, RLS, historical report/manifest or fixture evidence changes. Default disabled gates and normal simulation behavior are preserved.

## Focused mock-only acceptance

**126 passed, 0 failed, 0 skipped**, with two existing Starlette/AnyIO and LangGraph dependency warnings:

```text
.venv/bin/python -m pytest backend/tests/test_research_demo_budget.py \
  backend/tests/test_research.py backend/tests/test_research_contracts.py \
  backend/tests/test_llm_client.py -q
```

The budget suite has **66 cases** (33 prior + 33 added here). It uses the real installed SDK over in-memory HTTP transport, synthetic test-only keys and disposable SQLite. New checks cover admission-wide reservation persistence/exhaustion, overlapping admission, cancelled admission with already queued work, failed admission writes, no refunds on failure/cancellation/missing usage, exact request serialization, oversized generated Report input, unaccounted fields, unsupported topology, missing/forked/mismatched launcher authority, configuration drift, exclusion of a second local process and mocked launcher flags/cleanup. Prior transport tests retain the three-request success proof, zero-retry 429/500 failures, fourth-request rejection even with a hostile retry-enabled SDK, cancellation/partial evidence, monotonic expiry and historical checksum checks.

The other 60 cases cover directly relevant research admission/evidence/tenant gates and provider contracts. The earlier 167-test selection is historical baseline evidence; unrelated simulation/graph suites were not repeated. No frontend changed, so no frontend checks required. No new PostgreSQL/RLS, browser, real-provider or production result is inferred.

## Owner decision for an estimated-budget acceptance run

**Conditionally suitable for a small operational test, not for a hard-token/cost guarantee.** Before any real call the owner must explicitly authorize:

1. One dedicated loopback backend through the verified launcher, one isolated absolute-path SQLite database, one worker/replica, DEBUG/reload false, no restart or concurrent credential users/other application execution. Known hosted deployment markers must be absent because this is genuinely local, not removed to bypass checks.
2. Local credential handling and the exact `openai/gpt-oss-120b` model; one pinned B-direct experiment, Single + Adaptive, two trials; three HTTP attempts maximum, zero retries/judges/resume/reruns, 512 requested output tokens per call and 180 seconds total.
3. Explicit acceptance that **13056 input estimate units + 1536 output caps = 14592 estimated units is not a guaranteed token count or spending cap**; the 16384 observed-token check acts only after responses. Missing usage, hidden framing, reasoning, remote timeout/cancellation and account telemetry can leave actual usage unknown or above estimate. If that uncertainty is unacceptable, remain NO-GO until provider-certified preflight/rendering and output/usage contracts establish an enforceable bound.
4. Review persisted admission/attempt/usage/failure events and exact Task IDs after reload/export, compare provider account usage if separately authorized, preserve genuine partial evidence, keep it separate from the historical sample, and stop the dedicated backend immediately after the single test. Restart only with execution/judge gates disabled.

No owner authorization is implied by this report or commit. STOP for owner review before credential handling, a live Groq call, production connection, deployment or push.
