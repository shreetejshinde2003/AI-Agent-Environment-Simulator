"""Real SDK + in-memory HTTP transport; no credential or external network use."""
import asyncio
import hashlib
import json
from pathlib import Path

import httpx
import pytest
from fastapi import BackgroundTasks

from app.agents import llm_client
from app.api.routes import experiments, tasks
from app.core.config import settings
from app.experiments import demo_budget as demo
from app.models.schemas import ResearchExperimentInput, TaskStatus
from test_research import local

PROTOCOL = dict(benchmarkIds=["B-direct"], modes=["single", "adaptive"], repetitions=1)


@pytest.fixture(autouse=True)
def local_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "RESEARCH_DEMO_TOPOLOGY", "single_process_local")
    monkeypatch.setattr(settings, "RESEARCH_DEMO_REPLICAS", 1)
    monkeypatch.setattr(settings, "HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "DEBUG", False)
    for field in ("WEB_CONCURRENCY", "UVICORN_WORKERS", "RAILWAY_ENVIRONMENT_ID", "KUBERNETES_SERVICE_HOST", "VERCEL"):
        monkeypatch.setattr(settings, field, None)
    demo.claim_local_runtime("sqlite:///" + str(tmp_path / "research.db"))
    yield
    demo.release_local_runtime()


def reply(usage=True, output_tokens=7):
    body = dict(id="mock-chat", object="chat.completion", created=1, model="mock-model",
        choices=[dict(index=0, finish_reason="stop", message=dict(role="assistant", content="recovery time objective"))])
    if usage:
        body["usage"] = dict(prompt_tokens=11, completion_tokens=output_tokens, total_tokens=11 + output_tokens)
    return httpx.Response(200, json=body)


@pytest.fixture
def bounded(local, monkeypatch):
    monkeypatch.setattr(settings, "RESEARCH_DEMO_ENABLED", True)
    monkeypatch.setattr(settings, "RESEARCH_JUDGE_ENABLED", False)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "mock-only-not-a-credential")
    demo.ledgers.clear()
    requests = []
    async def handler(request):
        requests.append(request)
        return reply()
    transport = httpx.MockTransport(handler)
    # The production wrapper remains intact; replace only its inner network transport.
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: transport)
    yield local, requests
    demo.ledgers.clear()


def runs(repo, eid):
    return repo.research_tasks(workspace_id=repo.get_personal_workspace("USR-a")["id"],
        user_id="USR-a", experiment_id=eid)


def create(client):
    response = client.post("/api/v1/experiments/research", json=PROTOCOL)
    assert response.status_code == 201, response.text
    return response.json()["experimentId"]


def test_two_trials_three_actual_http_requests_shared_and_retained(bounded, monkeypatch):
    import groq
    sdk_options = []
    original = groq.AsyncGroq
    def sdk(**kwargs):
        sdk_options.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(groq, "AsyncGroq", sdk)
    (repo, client), requests = bounded
    eid = create(client)
    saved = runs(repo, eid)
    assert len(saved) == 2 and all(t.status == TaskStatus.COMPLETED for t in saved)
    assert len(requests) == demo.ledgers[eid].attempts == 3
    assert demo.ledgers[eid].transport_invocations == 3
    assert len(sdk_options) == 3 and all(option["max_retries"] == 0 for option in sdk_options)
    assert llm_client._client.chat.completions.create.await_count == 0
    assert all(json.loads(r.content)["max_tokens"] == 512 for r in requests)
    events = [json.loads(e.text) for t in saved for e in t.events if e.type == "demo_budget"]
    assert [e["attempts"] for e in events if e["outcome"] == "attempt_reserved"] == [1, 2, 3]
    assert demo.ledgers[eid].reported_tokens == 54
    assert demo.ledgers[eid].reported_input_tokens == 33 and demo.ledgers[eid].reported_output_tokens == 21
    assert all(t.research.configuration.retry_policy == "demo: zero SDK and transport retries" for t in saved)
    assert all(any(e.type == "demo_trial_completed" for e in t.events) for t in saved)
    exported = client.get(f"/api/v1/experiments/research/{eid}/report").json()
    assert len(exported["runEvidence"]) == 2
    assert client.post("/api/v1/experiments/research", json=PROTOCOL).status_code == 409
    assert client.post(f"/api/v1/experiments/research/{eid}/rerun").status_code == 422
    monkeypatch.setattr(settings, "RESEARCH_JUDGE_ENABLED", True)
    assert client.post(f"/api/v1/tasks/{saved[0].id}/evaluate").status_code == 403
    assert len(requests) == 3


@pytest.mark.parametrize("change", [dict(benchmarkIds=["B-synthesis"]), dict(modes=["single"]),
    dict(modes=["adaptive", "single"]), dict(modes=["single", "fixed", "adaptive"]), dict(repetitions=2)])
def test_protocol_rejects_other_admissions(bounded, change):
    (repo, client), requests = bounded
    assert client.post("/api/v1/experiments/research", json={**PROTOCOL, **change}).status_code == 422
    assert repo.list() == [] and requests == []


@pytest.mark.parametrize("status", [429, 500])
def test_sdk_http_failures_never_retry_and_stop_remaining_trials(bounded, monkeypatch, status):
    (repo, client), requests = bounded
    def handler(request):
        requests.append(request)
        return httpx.Response(status, json={"error": {"message": "mock failure"}})
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(handler))
    eid = create(client)
    assert len(requests) == demo.ledgers[eid].attempts == 1
    saved = runs(repo, eid)
    assert len(saved) == 2 and all(t.status == TaskStatus.FAILED and t.output is None for t in saved)
    assert demo.ledgers[eid].reserved > 0 and not demo.ledgers[eid].usage_complete
    assert any("provider_http_failure" in e.text for t in saved for e in t.events)


@pytest.mark.asyncio
async def test_boundary_itself_blocks_fourth_request_even_with_sdk_retries(monkeypatch):
    from groq import AsyncGroq
    budget = demo.DemoBudget("E-test", "W-test", "U-test", ("T-1", "T-2"))
    requests, events = [], []
    async def evidence(outcome):
        events.append(outcome)
    def handler(request):
        requests.append(request)
        return reply()
    transport = demo.BudgetTransport(budget, evidence, httpx.MockTransport(handler))
    async with httpx.AsyncClient(transport=transport) as http:
        # Deliberately hostile SDK configuration: boundary still owns admission.
        client = AsyncGroq(api_key="mock", max_retries=2, http_client=http)
        for _ in range(3):
            await client.chat.completions.create(model=demo.APPROVED_MODEL, messages=[dict(role="user", content="test")], max_tokens=512)
        with pytest.raises(Exception):
            await client.chat.completions.create(model=demo.APPROVED_MODEL, messages=[dict(role="user", content="test")], max_tokens=512)
    assert len(requests) == budget.attempts == 3
    assert "attempt_budget_exhausted" in events


@pytest.mark.parametrize("failure", ["cancelled", "timeout", "transport"])
def test_cancellation_timeout_transport_fail_closed_with_partial_evidence(bounded, monkeypatch, failure):
    (repo, client), requests = bounded
    async def handler(request):
        requests.append(request)
        if len(requests) == 2:
            if failure == "cancelled":
                raise asyncio.CancelledError()
            if failure == "timeout":
                raise TimeoutError()
            raise httpx.ConnectError("mock transport failure")
        return reply()
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(handler))
    eid = create(client)
    saved = runs(repo, eid)
    assert len(requests) == 2
    assert saved[0].output == "recovery time objective" and saved[1].output is None
    assert saved[1].status == TaskStatus.FAILED and saved[1].stages[1].started_at is None
    outcome = {"cancelled": "cancelled", "timeout": "deadline_exhausted", "transport": "transport_failure"}[failure]
    assert any(outcome in e.text for e in saved[1].events)
    assert any(e.type == "demo_trial_failed" for e in saved[1].events)


def test_expiry_between_trials_rejects_all_new_calls(bounded, monkeypatch):
    (repo, client), requests = bounded
    def handler(request):
        requests.append(request)
        next(iter(demo.ledgers.values())).deadline = 0
        return reply()
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(handler))
    eid = create(client)
    assert len(requests) == 1 and runs(repo, eid)[1].status == TaskStatus.FAILED
    assert any("deadline_exhausted" in e.text for t in runs(repo, eid) for e in t.events)


def test_monotonic_deadline_interrupts_inflight_request(bounded, monkeypatch):
    (repo, client), requests = bounded
    monkeypatch.setattr(demo, "DEADLINE_SECONDS", 0.1)
    async def handler(request):
        requests.append(request)
        await asyncio.Event().wait()
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(handler))
    eid = create(client)
    assert len(requests) == 1 and demo.ledgers[eid].stopped == "deadline_exhausted"
    assert all(t.status == TaskStatus.FAILED and t.output is None for t in runs(repo, eid))


def test_changed_approved_benchmark_is_rejected(bounded, monkeypatch):
    (repo, client), requests = bounded
    from app.experiments.research import catalog
    changed = catalog()[0].model_copy(update={"source": "changed glossary"})
    monkeypatch.setattr(experiments, "catalog", lambda: (changed,))
    assert client.post("/api/v1/experiments/research", json=PROTOCOL).status_code == 409
    assert requests == [] and repo.list() == []


def test_live_evidence_always_requires_bounded_protocol(bounded, monkeypatch):
    (repo, client), requests = bounded
    monkeypatch.setattr(settings, "RESEARCH_DEMO_ENABLED", False)
    monkeypatch.setattr(settings, "RESEARCH_EVIDENCE_KIND", "provider_live")
    assert client.post("/api/v1/experiments/research", json={**PROTOCOL, "repetitions": 2}).status_code == 422
    assert requests == [] and repo.list() == []


@pytest.mark.asyncio
async def test_missing_context_never_falls_back_to_normal_sdk(monkeypatch):
    token = llm_client.research_call_configuration.set(("mock", 512, True))
    context = demo.demo_context.set(None)
    try:
        with pytest.raises(RuntimeError):
            await llm_client.call_llm("test")
    finally:
        demo.demo_context.reset(context)
        llm_client.research_call_configuration.reset(token)


@pytest.mark.asyncio
async def test_reservation_persistence_failure_prevents_transport():
    budget = demo.DemoBudget("E-test", "W-test", "U-test", ("T-1", "T-2"))
    requests = []
    async def evidence(outcome):
        if outcome == "attempt_reserved":
            raise RuntimeError("mock writer unavailable")
    def handler(request):
        requests.append(request)
        return reply()
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions",
        json=dict(model=demo.APPROVED_MODEL, max_tokens=512, messages=[dict(role="user", content="test")]))
    with pytest.raises(demo.DemoBudgetError):
        await demo.BudgetTransport(budget, evidence, httpx.MockTransport(handler)).handle_async_request(request)
    assert requests == [] and budget.attempts == 1 and budget.transport_invocations == 0
    assert budget.stopped == "transport_failure"


@pytest.mark.asyncio
async def test_real_transport_constructed_with_zero_retries(monkeypatch):
    options = []
    def factory(**kwargs):
        options.append(kwargs)
        return httpx.MockTransport(lambda request: reply())
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", factory)
    async def evidence(outcome):
        pass
    transport = demo.BudgetTransport(demo.DemoBudget("E-test", "W-test", "U-test", ("T-1", "T-2")), evidence)
    await transport.aclose()
    assert options == [{"retries": 0}]


@pytest.mark.asyncio
async def test_concurrent_streamed_requests_cannot_overreserve_shared_attempts():
    budget = demo.DemoBudget("E-test", "W-test", "U-test", ("T-1", "T-2"))
    ready = asyncio.Event()
    arrivals, requests = [], []
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            arrivals.append(True)
            if len(arrivals) == 4:
                ready.set()
            await ready.wait()
            yield json.dumps(dict(model=demo.APPROVED_MODEL, max_tokens=512,
                messages=[dict(role="user", content="test")])).encode()
    async def evidence(outcome):
        await asyncio.sleep(0)
    def handler(request):
        requests.append(request)
        return reply()
    transport = demo.BudgetTransport(budget, evidence, httpx.MockTransport(handler))
    results = await asyncio.gather(*(transport.handle_async_request(httpx.Request("POST",
        "https://api.groq.com/openai/v1/chat/completions", stream=Body())) for _ in range(4)),
        return_exceptions=True)
    assert budget.attempts == 3 and len(requests) <= 3
    assert any(isinstance(result, demo.DemoBudgetError) for result in results)


@pytest.mark.parametrize("usage,output_tokens", [(False, 7), (True, 513), (True, 20000)])
def test_usage_is_observable_policy_not_hard_token_bound(bounded, monkeypatch, usage, output_tokens):
    (repo, client), requests = bounded
    def handler(request):
        requests.append(request)
        return reply(usage=usage, output_tokens=output_tokens)
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(handler))
    eid = create(client)
    saved = runs(repo, eid)
    assert len(requests) == 1 and saved[1].output is None
    assert demo.ledgers[eid].reserved > 0
    if not usage:
        assert saved[0].stages[0].total_tokens is None
        assert not demo.ledgers[eid].usage_complete
        assert saved[0].output == "recovery time objective"
    else:
        assert saved[0].output is None
        assert demo.ledgers[eid].reported_tokens == 11 + output_tokens


@pytest.mark.asyncio
@pytest.mark.parametrize("condition", ["expired", "oversized", "reservation", "wrong_endpoint", "output_cap"])
async def test_pretransport_rejections_send_nothing(condition):
    budget = demo.DemoBudget("E-test", "W-test", "U-test", ("T-1", "T-2"))
    requests = []
    async def evidence(outcome):
        pass
    def handler(request):
        requests.append(request)
        return reply()
    if condition == "expired":
        budget.deadline = 0
    if condition == "reservation":
        budget.reserved = demo.RESERVATION_LIMIT
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/" +
        ("models" if condition == "wrong_endpoint" else "chat/completions"),
        json=dict(model=demo.APPROVED_MODEL, max_tokens=1024 if condition == "output_cap" else 512,
            messages=[dict(role="user", content="x" * (4096 if condition == "oversized" else 1))]))
    with pytest.raises(demo.DemoBudgetError):
        await demo.BudgetTransport(budget, evidence, httpx.MockTransport(handler)).handle_async_request(request)
    assert requests == [] and budget.attempts == 0


@pytest.mark.parametrize("state", ["missing", "wrong_tenant", "expired"])
def test_lost_or_mismatched_admitted_budget_fails_closed(bounded, state):
    (repo, _), requests = bounded
    workspace = repo.get_personal_workspace("USR-a")["id"]
    bg = BackgroundTasks()
    admitted = asyncio.run(experiments.admit_research(ResearchExperimentInput.model_validate(PROTOCOL),
        bg, workspace_id=workspace, user_id="USR-a"))
    eid = admitted["experimentId"]
    if state == "missing":
        demo.ledgers.clear()
    elif state == "wrong_tenant":
        demo.ledgers[eid].workspace_id = "other"
    else:
        demo.ledgers[eid].deadline = 0
    asyncio.run(bg())
    assert requests == [] and all(t.status == TaskStatus.FAILED for t in runs(repo, eid))


def test_gate_auth_tenant_and_judge_guards(bounded, monkeypatch):
    (repo, client), requests = bounded
    monkeypatch.setattr(settings, "RESEARCH_LIVE_ENABLED", False)
    assert client.post("/api/v1/experiments/research", json=PROTOCOL).status_code == 403
    monkeypatch.setattr(settings, "RESEARCH_LIVE_ENABLED", True)
    monkeypatch.setattr(settings, "RESEARCH_JUDGE_ENABLED", True)
    assert client.post("/api/v1/experiments/research", json=PROTOCOL).status_code == 403
    monkeypatch.setattr(settings, "RESEARCH_JUDGE_ENABLED", False)
    other = repo.get_personal_workspace("USR-b")["id"]
    assert client.post("/api/v1/experiments/research", json=PROTOCOL, headers={"X-Workspace-Id": other}).status_code == 404
    client.cookies.clear()
    assert client.post("/api/v1/experiments/research", json=PROTOCOL).status_code == 401
    assert requests == [] and repo.list() == []


def test_historical_sample_provenance_is_unchanged():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "frontend/public/examples/research-fixture-manifest.json").read_text())
    sample = root / "frontend/public/examples/research-fixture-report.json"
    original = root / "docs/acceptance/phase10-fixture-report.json"
    assert sample.read_bytes() == original.read_bytes()
    assert hashlib.sha256(sample.read_bytes()).hexdigest() in json.dumps(manifest)


def test_admission_reserves_all_future_input_and_output_before_execution(bounded):
    (repo, _), requests = bounded
    bg = BackgroundTasks()
    admitted = asyncio.run(experiments.admit_research(ResearchExperimentInput.model_validate(PROTOCOL), bg,
        workspace_id=repo.get_personal_workspace("USR-a")["id"], user_id="USR-a"))
    budget = demo.ledgers[admitted["experimentId"]]
    assert (budget.admitted_input_units, budget.admitted_output_tokens, budget.admitted_total_units) == (13056, 1536, 14592)
    assert budget.attempts == budget.reserved == 0 and requests == []
    for task in runs(repo, admitted["experimentId"]):
        event = next(e for e in task.events if e.type == "demo_budget_admitted")
        evidence = json.loads(event.text)
        assert evidence["admittedTotalEstimateUnits"] == 14592
        assert evidence["hardTotalTokenGuarantee"] is False
    asyncio.run(bg())
    assert len(requests) == 3 and budget.reserved <= budget.admitted_total_units


def test_admission_reservation_exhaustion_persists_no_trials(bounded, monkeypatch):
    (repo, client), requests = bounded
    monkeypatch.setattr(demo, "RESERVATION_LIMIT", 14591)
    response = client.post("/api/v1/experiments/research", json=PROTOCOL)
    assert response.status_code == 422 and "admission_reservation_budget_exhausted" in response.text
    assert requests == [] and repo.list() == [] and demo.ledgers == {}


@pytest.mark.asyncio
async def test_overlapping_admissions_admit_exactly_one_experiment(bounded, monkeypatch):
    from fastapi import HTTPException
    (repo, _), requests = bounded
    entered, release = asyncio.Event(), asyncio.Event()
    original = experiments.enqueue_task
    async def overlapping(*args, **kwargs):
        entered.set()
        await release.wait()
        return await original(*args, **kwargs)
    monkeypatch.setattr(experiments, "enqueue_task", overlapping)
    bg = BackgroundTasks()
    params = dict(workspace_id=repo.get_personal_workspace("USR-a")["id"], user_id="USR-a")
    first = asyncio.create_task(experiments.admit_research(ResearchExperimentInput.model_validate(PROTOCOL), bg, **params))
    await entered.wait()
    try:
        with pytest.raises(HTTPException) as error:
            await experiments.admit_research(ResearchExperimentInput.model_validate(PROTOCOL), BackgroundTasks(), **params)
        assert error.value.status_code == 409
    finally:
        release.set()
    admitted = await first
    assert len(repo.list()) == 2 and len(demo.ledgers) == 1
    await bg()
    assert len(requests) == 3 and len(runs(repo, admitted["experimentId"])) == 2


@pytest.mark.asyncio
async def test_cancelled_admission_stops_already_queued_work(bounded, monkeypatch):
    from fastapi import HTTPException
    (repo, _), requests = bounded
    entered = asyncio.Event()
    original = experiments.enqueue_task
    async def enqueue_then_wait(*args, **kwargs):
        result = await original(*args, **kwargs)
        entered.set()
        await asyncio.Event().wait()
        return result
    monkeypatch.setattr(experiments, "enqueue_task", enqueue_then_wait)
    bg = BackgroundTasks()
    params = dict(workspace_id=repo.get_personal_workspace("USR-a")["id"], user_id="USR-a")
    admission = asyncio.create_task(experiments.admit_research(ResearchExperimentInput.model_validate(PROTOCOL), bg, **params))
    await entered.wait()
    admission.cancel()
    with pytest.raises(asyncio.CancelledError):
        await admission
    eid = next(iter(demo.ledgers))
    assert demo.ledgers[eid].stopped == "admission_cancelled"
    assert all(t.status == TaskStatus.FAILED and t.output is None for t in runs(repo, eid))
    assert all(any("admission_cancelled" in event.text for event in t.events) for t in runs(repo, eid))
    with pytest.raises(HTTPException) as error:
        await experiments.admit_research(ResearchExperimentInput.model_validate(PROTOCOL), BackgroundTasks(), **params)
    assert error.value.status_code == 409
    await bg()
    assert requests == [] and demo.ledgers[eid].admitted_total_units == 14592


def test_failed_admission_write_consumes_authority(bounded, monkeypatch):
    (repo, _), requests = bounded
    def fail(*args, **kwargs):
        raise RuntimeError("mock write failure")
    monkeypatch.setattr(repo, "save_research_group", fail)
    params = dict(workspace_id=repo.get_personal_workspace("USR-a")["id"], user_id="USR-a")
    with pytest.raises(RuntimeError):
        asyncio.run(experiments.admit_research(ResearchExperimentInput.model_validate(PROTOCOL), BackgroundTasks(), **params))
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        asyncio.run(experiments.admit_research(ResearchExperimentInput.model_validate(PROTOCOL), BackgroundTasks(), **params))
    assert error.value.status_code == 409 and requests == [] and repo.list() == []


@pytest.mark.parametrize("field,value", [("RESEARCH_DEMO_TOPOLOGY", "unsupported"),
    ("RESEARCH_DEMO_REPLICAS", 0), ("RESEARCH_DEMO_REPLICAS", 2), ("WEB_CONCURRENCY", 2),
    ("UVICORN_WORKERS", 2), ("HOST", "0.0.0.0"), ("DEBUG", True),
    ("RAILWAY_ENVIRONMENT_ID", "mock-hosted"), ("KUBERNETES_SERVICE_HOST", "mock-hosted"), ("VERCEL", "1")])
def test_unsupported_topology_rejects_before_admission(bounded, monkeypatch, field, value):
    (repo, client), requests = bounded
    monkeypatch.setattr(settings, field, value)
    assert client.post("/api/v1/experiments/research", json=PROTOCOL).status_code == 403
    assert requests == [] and repo.list() == []


@pytest.mark.parametrize("state", ["missing", "fork", "different_database"])
def test_launcher_authority_cannot_be_reused(bounded, monkeypatch, state):
    (repo, client), requests = bounded
    if state == "missing":
        demo.release_local_runtime()
    elif state == "fork":
        demo.runtime_lease["pid"] = -1
    else:
        demo.runtime_lease["database"] = Path("/other-database.db")
    assert client.post("/api/v1/experiments/research", json=PROTOCOL).status_code == 403
    assert requests == [] and repo.list() == []


def test_database_lock_excludes_second_local_process(tmp_path):
    import subprocess
    # Second isolated local Python process attempts only the same advisory lock.
    code = """import fcntl, sys
with open(sys.argv[1], 'a+') as lock:
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(3)
"""
    import sys
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path / "research.db.research-demo.lock")], check=False)
    assert result.returncode == 3


def test_topology_drift_before_later_request_stops_transport(bounded, monkeypatch):
    (repo, client), requests = bounded
    def handler(request):
        requests.append(request)
        monkeypatch.setattr(settings, "RESEARCH_DEMO_REPLICAS", 2)
        return reply()
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(handler))
    eid = create(client)
    assert len(requests) == 1 and runs(repo, eid)[1].status == TaskStatus.FAILED
    assert demo.ledgers[eid].admitted_total_units == 14592


@pytest.mark.parametrize("outcome", ["http_error", "cancelled", "missing_usage"])
def test_admission_reservations_never_refunded(bounded, monkeypatch, outcome):
    (repo, client), requests = bounded
    async def handler(request):
        requests.append(request)
        if outcome == "cancelled":
            raise asyncio.CancelledError()
        if outcome == "http_error":
            return httpx.Response(500, json={"error": {"message": "mock failure"}})
        return reply(usage=False)
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(handler))
    eid = create(client)
    budget = demo.ledgers[eid]
    assert budget.admitted_total_units == 14592 and budget.reserved > 0
    assert len(requests) == 1 and not budget.usage_complete
    assert client.post("/api/v1/experiments/research", json=PROTOCOL).status_code == 409


def test_generated_upstream_text_cannot_bypass_report_preflight(bounded, monkeypatch):
    (repo, client), requests = bounded
    def handler(request):
        requests.append(request)
        response = reply()
        if len(requests) == 2:
            body = response.json()
            body["choices"][0]["message"]["content"] = "界" * 2000
            return httpx.Response(200, json=body)
        return response
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(handler))
    eid = create(client)
    assert len(requests) == 2
    adaptive = runs(repo, eid)[1]
    assert adaptive.output is None and adaptive.stages[0].output == "界" * 2000
    assert demo.ledgers[eid].stopped == "request_budget_rejected"


def test_exact_sdk_serialization_is_accounted_at_boundary(bounded, monkeypatch):
    (repo, client), requests = bounded
    eid = create(client)
    for request in requests:
        payload = json.loads(request.content)
        assert set(payload) == {"model", "messages", "max_tokens"}
        assert payload["model"] == "openai/gpt-oss-120b" and payload["max_tokens"] == 512
        assert [message["role"] for message in payload["messages"]] == ["system", "user"]
    assert demo.ledgers[eid].reserved == sum(len(r.content) + 256 + 512 for r in requests)


@pytest.mark.asyncio
@pytest.mark.parametrize("extra", [dict(tools=[]), dict(documents=[]), dict(functions=[]), dict(n=2),
    dict(reasoning_effort="high"), dict(max_completion_tokens=2048)])
async def test_unaccounted_request_fields_fail_closed(extra):
    budget = demo.DemoBudget("E-test", "W-test", "U-test", ("T-1", "T-2"))
    async def evidence(outcome):
        pass
    requests = []
    def handler(request):
        requests.append(request)
        return reply()
    payload = dict(model=demo.APPROVED_MODEL, max_tokens=512, messages=[dict(role="user", content="test")], **extra)
    with pytest.raises(demo.DemoBudgetError):
        await demo.BudgetTransport(budget, evidence, httpx.MockTransport(handler)).handle_async_request(
            httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions", json=payload))
    assert requests == [] and budget.attempts == 0


@pytest.mark.parametrize("enabled", [False, True])
def test_launcher_preserves_disabled_behavior_and_fixes_demo_topology(tmp_path, monkeypatch, enabled):
    import runpy
    import uvicorn
    demo.release_local_runtime()
    monkeypatch.setattr(settings, "RESEARCH_LIVE_ENABLED", enabled)
    monkeypatch.setattr(settings, "RESEARCH_EVIDENCE_KIND", "provider_live")
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///" + str(tmp_path / "research.db"))
    if not enabled:
        monkeypatch.setattr(settings, "DEBUG", True)
        monkeypatch.setattr(settings, "HOST", "0.0.0.0")
        monkeypatch.setattr(settings, "RESEARCH_DEMO_TOPOLOGY", "unsupported")
    calls = []
    def server(*args, **kwargs):
        calls.append(kwargs)
        if enabled:
            demo.require_local_runtime(settings.DATABASE_URL)
        else:
            assert demo.runtime_lease is None
    monkeypatch.setattr(uvicorn, "run", server)
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "run.py"), run_name="__main__")
    assert calls[0]["workers"] == (1 if enabled else None)
    assert calls[0]["reload"] is (not enabled)
    assert demo.runtime_lease is None
