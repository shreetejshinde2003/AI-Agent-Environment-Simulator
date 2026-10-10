# Minimal Research demonstration readiness — 2026-10-10

Baseline: local `main`, `75c99639872616af2c2d6e0cef2c4822943fd38f`; matched actual checkout. **Historical demonstration: ready from existing local evidence. Real bounded demonstration: NO-GO until request/usage enforcement is corrected and separately approved.** No provider gate, credential, production setting, schema or runtime behavior was changed during preparation.

## A. Historical presentation

Research Lab → Explore a sample experiment → select a stored trial. This reads `frontend/public/examples/research-fixture-report.json`, an unchanged copy of the legitimate 42-trial Phase-10 report, checked against its manifest. It is explicitly historical, deterministic and read-only; it creates no new workspace runs or provider calls. Inspect inputs, raw answers, stage/route evidence and descriptive results. Fixture success is not model accuracy, live latency, pricing, training or comparative superiority.

## B. Verified live path and bounds

| Concern | Actual implementation / implication |
|---|---|
| Admission | `api/routes/experiments.py:create_research` requires authenticated `SIMULATION_CREATE` in the selected workspace. `admit_research` rejects a false `RESEARCH_LIVE_ENABLED` before preparation/persistence. Rerun uses the same gate. Server validation permits 1–7 unique cases, Single/Fixed/Adaptive subsets, 1–5 repetitions, at most 45 trials. |
| Worker gate | `api/routes/tasks.py:_run_stage` checks live gate and pinned configuration again before every research stage. Disabling admission alone does not cancel an already submitted remote request. |
| Scope | `B-direct` v1, Single + Adaptive, one repetition: exactly **two Tasks**. Single executes Direct; deterministic `rules-v1` Adaptive routing executes Research → Report, skipping Data/Analysis/Summarizer. Router/orchestrator makes no LLM call. |
| Provider | `agents/llm_client.py` central Groq adapter; all six implemented system agents currently have `MODEL=None`, resolving to **openai/gpt-oss-120b** in this local configuration. Fast setting is **openai/gpt-oss-20b**, unused for these three stages. Model availability was not verified by a live request. Sampling is provider-default with no seed guarantee. |
| Requests | **Three SDK completion calls** for a fresh successful demonstration, not two. Installed Groq defaults permit **2 retries per call**, so up to **9 HTTP attempts** for those three stages. Failed requests can consume remote work without returning usage. Stage-start metrics do not measure HTTP attempts. |
| Evaluation | Automatic evaluation is deterministic and costs zero model requests. Human rubric scoring costs zero. Explicit `/tasks/{id}/evaluate` requires `SIMULATION_EVALUATE` and `RESEARCH_JUDGE_ENABLED`; leave it false. Enabling one judge call for each trial could add 2 SDK calls / up to 6 HTTP attempts, making 15 for that initial protocol. There is no experiment-wide lifetime budget across new reruns/resumes/evaluation. |
| Tokens/time | Research pins **1024 maximum output tokens per completion**, giving 3072 requested output-token capacity across three successful calls; this is not a total billable-token cap. Input/handoff character bounds exist, not a tokenizer-backed input-token reservation. SDK defaults are 60-second network timeout / 5-second connect timeout per attempt, not a hard experiment wall-clock deadline. No enforced monetary or experiment-wide token ceiling exists. |
| Failure/cancellation | Exceptions and cancellation produce failed stages/tasks, no fabricated final output, retained events/timing, and downstream nonexecution; other trials can continue. Sanitized errors can conceal timeout/cancellation cause. Cancellation does not prove remote computation was cancelled. Restart recovery records failure; durable graph resume needs its existing checkpoint authorization/configuration and can create additional attempts. |
| Storage | Atomic `Repository.save_research_group` uses the tenant transaction before enqueue. Each trial pins configuration, benchmark/checksum, provenance, run IDs and experiment ID in the genuine Task payload (`simulations.payload`), with `tasks` projections and normalized `agent_executions` rows. RoutePlan is retained in the Task payload, not a separate research database/table. All reads/export use workspace authorization; no schema migration required for this flow. |
| History/export | List/detail/report endpoints read retained repository records, independent of page state. Export contains full Task/stage/route/output evidence and derived metrics. Missing usage/cost/retry data remain unknown. `complete` means all expected trials are terminal, including failed trials; missing records/inconsistent provenance prevent comparability. One repetition per mode supports descriptive observations only. |
| Local enablement | Configuration is process-scoped: a separately started normal local demo backend can use its own database and settings while production stays untouched. No special secure demo-only admission endpoint or one-experiment gate exists. Test fixtures replace the provider and provenance and must never be reused to claim real execution. |

Inspected local effective settings: live gate **false**, judge **false**, LangGraph **false**. Sequential runtime is sufficient for the proposed protocol; no new checkpoint setup is needed. Frontend already confirms case × modes × repetitions before admission, discloses provider usage, separates sample/history and offers exact saved evidence navigation. It cannot enforce a spending limit on its own.

## C. Deterministic acceptance

`backend/tests/test_research.py`: **47 passed, 0 failed, 0 skipped** (two existing Starlette/AnyIO and LangGraph dependency warnings). New acceptance runs one B-direct case × Single/Adaptive × one repetition against disposable SQLite with mocked SDK output, checking:

- two unique persisted Tasks, matching output and provenance; Direct versus Research/Report stages and Adaptive RoutePlan;
- three SDK calls with pinned models/1024 limits, normalized stage/task rows, genuine saved outputs and usage;
- identical retained records through a new repository connection, saved history, repeat exports, unknown costs/retries and cross-tenant 404s;
- cancelled first provider attempt retains failure while the other trial completes; no false all-success inference.

The existing suite also verifies gate/judge rejection without provider calls, invalid admission, atomic pending/incomplete states, failure continuation, permission revocation, missing evidence, provenance/configuration drift and honest recovery/retry metrics. The new successful protocol blocks HTTPX async transport and observes **zero external requests**. All execution tests use mocked providers; the real gate is altered only by isolated test monkeypatches and restored afterwards, never enabled for a real provider.

No new browser/PostgreSQL/live-provider acceptance is claimed. Previously verified fixture checksum/browser/RLS results remain historical. No frontend changed, so lint/build was not repeated.

## D. Required correction and approval checklist — do not execute yet

Smallest necessary correction: retain an experiment-wide attempt budget in existing research evidence, reserve it atomically before every provider call (including resume and judge paths), explicitly set SDK retries to zero for the demo, pin per-call and experiment deadlines, and reserve a conservative/model-validated input plus output token ceiling before sending. Unknown usage must not release reservations; repeated clicks/reruns must not bypass the authorized scope. Record attempts/failures without secrets. This may fit existing schema-14 JSON payloads, but requires implementation/review/tests first; no unverified migration or budget workaround was introduced here.

Owner must approve the following concrete protocol **only after that correction passes**:

1. **Environment:** dedicated loopback-only normal local backend and isolated demo database, authenticated through the normal application. No production connection. Explicitly approve any local credential configuration and real Google sign-in separately if needed. Keep sequential runtime; gate false until the approved run; judge false throughout.
2. **Experiment:** B-direct v1, modes exactly `[single, adaptive]`, repetitions 1, one admission only. Review original glossary/source, configuration fingerprint and confirmation showing two trials. No Fixed, rerun, resume, judge or unrelated simulation execution during the demo.
3. **Proposed hard budget (not yet enforced):** default model openai/gpt-oss-120b for Direct/Research/Report, 1024 output tokens per request; **3 provider attempts total, zero retries, zero judge calls**; a proposed **16384 total input+output token reservation** and **180-second experiment deadline**. Approve model availability and tokenizer/conservative accounting before accepting this ceiling. Current code cannot promise this budget.
4. **Verification:** inspect server attempt reservations and provider-returned per-stage model/input/output/total usage plus provider account usage. Failed/timeout usage remains conservatively reserved/unknown; never infer zero cost from missing telemetry. Capture the real `provider_live` configuration/Task identities and export the report after reload.
5. **Disable:** stop only the dedicated local demo backend to prevent further local calls, then restart it with live/judge gates false. There is no in-app kill switch; already accepted remote work may continue. Do not recycle/purge evidence or edit production to disable this local demo.
6. **Inspect:** Research Lab → Your saved experiments → exact trial → Open run evidence, raw output/stages/route; inspect usage/failure coverage and export both trials. Separate this genuine report from the 42-trial historical sample. Preserve history even if one/both trials fail.

**Approval required before the first live call:** explicit authorization for this isolated environment, credential handling, model, single experiment and enforced maximum attempts/tokens/time, with judges/retries/reruns excluded. Approval of this report alone does not enable execution. Stop for owner review; no push or deployment.
