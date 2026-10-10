"""Process-local, fail-closed demo ledger. Persist evidence in existing Task events.

Byte reservations are an admission policy, NOT a verified model token upper bound.
Restart/resume cannot reconstruct authority from saved events. Never replenish a ledger.
"""
import asyncio
import json
import os
import threading
import time
from pathlib import Path
from contextvars import ContextVar
from dataclasses import dataclass, field

import httpx

from app.core.config import settings

MAX_ATTEMPTS = 3
MAX_OUTPUT_TOKENS = 512
MAX_REQUEST_BYTES = 4096
RESERVATION_LIMIT = 16384
CHAT_OVERHEAD_UNITS = 256  # Estimated margin, not a provider-certified template count.
APPROVED_MODEL = "openai/gpt-oss-120b"
DEADLINE_SECONDS = 180
APPROVED_BENCHMARK_SHA256 = "2153e664f10f4cd0d412729ce842ab0165c8ed7b528500f2192c2f44d6ed379f"
demo_context = ContextVar("demo_context", default=None)
ledgers = {}
admission_lock = threading.Lock()
runtime_lease = None


def bounded_demo():
    return settings.RESEARCH_DEMO_ENABLED or settings.RESEARCH_EVIDENCE_KIND == "provider_live"


class DemoBudgetError(RuntimeError):
    pass


def claim_local_runtime(database_url):
    """Only the explicit one-worker, no-reload local launcher grants this lease.

    Advisory lock excludes local processes sharing the DB; PID rejects inherited
    authority after fork. It is not an account-wide or cross-host credential lock.
    """
    global runtime_lease
    verify_local_configuration()
    if runtime_lease is not None:
        raise DemoBudgetError("demo_runtime_already_claimed")
    if not database_url.startswith("sqlite:///"):
        raise DemoBudgetError("demo_requires_local_sqlite")
    database_path = Path(database_url.removeprefix("sqlite:///"))
    if not database_path.is_absolute() or database_path.name == ":memory:":
        raise DemoBudgetError("demo_requires_absolute_isolated_database")
    import fcntl
    database_path = database_path.resolve()
    lock_file = database_path.with_name(database_path.name + ".research-demo.lock").open("a+")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        raise DemoBudgetError("demo_database_process_lock_unavailable") from None
    runtime_lease = dict(pid=os.getpid(), file=lock_file, consumed=False, database=database_path.resolve())


def verify_local_configuration():
    if (settings.RESEARCH_DEMO_TOPOLOGY != "single_process_local"
            or settings.RESEARCH_DEMO_REPLICAS != 1
            or settings.WEB_CONCURRENCY not in (None, 1)
            or settings.UVICORN_WORKERS not in (None, 1)
            or settings.HOST not in {"127.0.0.1", "::1"} or settings.DEBUG
            or settings.RAILWAY_ENVIRONMENT_ID or settings.KUBERNETES_SERVICE_HOST or settings.VERCEL):
        raise DemoBudgetError("unsupported_demo_deployment_topology")


def require_local_runtime(database_url=None):
    verify_local_configuration()
    if (runtime_lease is None or runtime_lease["pid"] != os.getpid()
            or runtime_lease["file"].closed):
        raise DemoBudgetError("missing_single_process_launcher_authority")
    if database_url is not None and (not database_url.startswith("sqlite:///") or
            Path(database_url.removeprefix("sqlite:///")).resolve() != runtime_lease["database"]):
        raise DemoBudgetError("demo_database_does_not_match_launcher")


def release_local_runtime():
    global runtime_lease
    if runtime_lease is not None:
        runtime_lease["file"].close()
        runtime_lease = None


@dataclass
class DemoBudget:
    experiment_id: str
    workspace_id: str
    user_id: str
    run_ids: tuple[str, ...]
    deadline: float = field(default_factory=lambda: time.monotonic() + DEADLINE_SECONDS)
    attempts: int = 0
    transport_invocations: int = 0
    reserved: int = 0
    reported_tokens: int = 0
    reported_input_tokens: int = 0
    reported_output_tokens: int = 0
    usage_complete: bool = True
    stopped: str | None = None
    admitted_input_units: int = field(init=False)
    admitted_output_tokens: int = field(init=False)
    admitted_total_units: int = field(init=False)

    def __post_init__(self):
        # Hold capacity for ALL requests before atomic two-trial admission,
        # including Report whose upstream text cannot yet be known. No refunds.
        self.admitted_input_units = MAX_ATTEMPTS * (MAX_REQUEST_BYTES + CHAT_OVERHEAD_UNITS)
        self.admitted_output_tokens = MAX_ATTEMPTS * MAX_OUTPUT_TOKENS
        self.admitted_total_units = self.admitted_input_units + self.admitted_output_tokens
        if self.admitted_total_units > RESERVATION_LIMIT:
            raise DemoBudgetError("admission_reservation_budget_exhausted")

    def check(self):
        if self.stopped:
            raise DemoBudgetError(self.stopped)
        if time.monotonic() >= self.deadline:
            self.stopped = "deadline_exhausted"
            raise DemoBudgetError(self.stopped)
        if self.attempts >= MAX_ATTEMPTS:
            raise DemoBudgetError("attempt_budget_exhausted")

    def snapshot(self, outcome):
        return json.dumps(dict(policy="bounded-demo-v1", outcome=outcome,
            attempts=self.attempts, maxAttempts=MAX_ATTEMPTS, reservedUnits=self.reserved,
            attemptMeasurement="transport reservations; pre-send failure can consume a slot",
            transportInvocations=self.transport_invocations,
            reservationLimit=RESERVATION_LIMIT, reservationMeasurement="request bytes + 256 margin + output token cap; estimated units",
            admittedInputEstimateUnits=self.admitted_input_units,
            admittedOutputTokens=self.admitted_output_tokens, admittedTotalEstimateUnits=self.admitted_total_units,
            inputAccounting="serialized request bytes + 256 margin per request; estimate, not model tokens",
            hardTotalTokenGuarantee=False,
            providerReportedTokens=self.reported_tokens, usageComplete=self.usage_complete,
            providerReportedInputTokens=self.reported_input_tokens,
            providerReportedOutputTokens=self.reported_output_tokens,
            maxOutputTokens=MAX_OUTPUT_TOKENS, deadlineSeconds=DEADLINE_SECONDS,
            stopped=self.stopped), sort_keys=True)


class BudgetTransport(httpx.AsyncBaseTransport):
    """Reserve immediately before the sole zero-retry HTTP transport invocation."""
    def __init__(self, budget, evidence, inner=None):
        self.budget = budget
        self.evidence = evidence
        self.inner = inner if inner is not None else httpx.AsyncHTTPTransport(retries=0)

    async def handle_async_request(self, request):
        budget = self.budget
        try:
            budget.check()
            require_local_runtime()
            if (request.method != "POST" or request.url.scheme != "https" or request.url.port not in (None, 443)
                    or request.url.query or request.url.host != "api.groq.com"
                    or request.url.path != "/openai/v1/chat/completions"):
                raise DemoBudgetError("unapproved_provider_request")
            body = await request.aread()
            payload = json.loads(body)
            if (not isinstance(payload, dict) or set(payload) != {"model", "messages", "max_tokens"}
                    or payload["model"] != APPROVED_MODEL
                    or not isinstance(payload["messages"], list) or not payload["messages"]
                    or any(not isinstance(message, dict) or set(message) != {"role", "content"}
                        or message["role"] not in {"system", "user"} or not isinstance(message["content"], str)
                        for message in payload["messages"])
                    or len(body) > MAX_REQUEST_BYTES or payload.get("max_tokens") != MAX_OUTPUT_TOKENS):
                raise DemoBudgetError("request_budget_rejected")
            reservation = len(body) + CHAT_OVERHEAD_UNITS + MAX_OUTPUT_TOKENS
            # Reading a streamed body may yield. Recheck all shared state here.
            budget.check()
            if budget.reserved + reservation > budget.admitted_total_units:
                raise DemoBudgetError("reservation_budget_exhausted")
            # No await between shared checks and reservation: atomic in this event loop.
            budget.attempts += 1
            budget.reserved += reservation
            # Persist BEFORE network. A failed writer prevents the transport invocation.
            await self.evidence("attempt_reserved")
            require_local_runtime()
            if budget.stopped:
                raise DemoBudgetError(budget.stopped)
            if time.monotonic() >= budget.deadline:
                raise DemoBudgetError("deadline_exhausted")
            async with asyncio.timeout(max(0, budget.deadline - time.monotonic())):
                budget.transport_invocations += 1
                response = await self.inner.handle_async_request(request)
                await response.aread()
            if response.status_code >= 400:
                budget.usage_complete = False
                budget.stopped = "provider_http_failure"
                await self.evidence("provider_http_failure")
            return response
        except (Exception, asyncio.CancelledError) as exc:
            budget.stopped = ("deadline_exhausted" if isinstance(exc, TimeoutError) or time.monotonic() >= budget.deadline else
                "cancelled" if isinstance(exc, asyncio.CancelledError) else
                str(exc) if isinstance(exc, DemoBudgetError) else "transport_failure")
            budget.usage_complete = False
            await self.evidence(budget.stopped)
            raise DemoBudgetError(budget.stopped) from None

    async def aclose(self):
        await self.inner.aclose()


async def demo_completion(model, messages):
    from groq import AsyncGroq
    binding = demo_context.get()
    if binding is None:
        raise DemoBudgetError("missing_budget_state")
    budget, evidence = binding
    try:
        require_local_runtime()
        if model != APPROVED_MODEL:
            raise DemoBudgetError("unapproved_demo_model")
        budget.check()
        async with asyncio.timeout(max(0, budget.deadline - time.monotonic())):
            async with httpx.AsyncClient(transport=BudgetTransport(budget, evidence),
                    follow_redirects=False, trust_env=False) as http_client:
                async with AsyncGroq(api_key=settings.GROQ_API_KEY, max_retries=0,
                        http_client=http_client) as client:
                    response = await client.chat.completions.create(model=model,
                        messages=messages, max_tokens=MAX_OUTPUT_TOKENS)
        usage = response.usage
        if usage is None or usage.prompt_tokens is None or usage.completion_tokens is None:
            budget.usage_complete = False
            budget.stopped = "usage_unavailable"
        else:
            budget.reported_input_tokens += usage.prompt_tokens
            budget.reported_output_tokens += usage.completion_tokens
            budget.reported_tokens += usage.prompt_tokens + usage.completion_tokens
            if (usage.prompt_tokens < 0 or usage.completion_tokens < 0
                    or usage.completion_tokens > MAX_OUTPUT_TOKENS
                    or budget.reported_tokens > RESERVATION_LIMIT):
                budget.stopped = "reported_usage_budget_exhausted"
        if time.monotonic() >= budget.deadline:
            budget.stopped = "deadline_exhausted"
        await evidence(budget.stopped or "provider_completed")
        if budget.stopped in {"reported_usage_budget_exhausted", "deadline_exhausted"}:
            raise DemoBudgetError(budget.stopped)
        return response
    except (Exception, asyncio.CancelledError) as exc:
        budget.stopped = budget.stopped or ("deadline_exhausted" if isinstance(exc, TimeoutError) or time.monotonic() >= budget.deadline
            else "cancelled" if isinstance(exc, asyncio.CancelledError) else
            str(exc) if isinstance(exc, DemoBudgetError) else "provider_failure")
        budget.usage_complete = False
        await evidence(budget.stopped)
        raise DemoBudgetError(budget.stopped) from None
