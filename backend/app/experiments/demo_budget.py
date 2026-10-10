"""Process-local, fail-closed demo ledger. Persist evidence in existing Task events.

Byte reservations are an admission policy, NOT a verified model token upper bound.
Restart/resume cannot reconstruct authority from saved events. Never replenish a ledger.
"""
import asyncio
import json
import time
from contextvars import ContextVar
from dataclasses import dataclass, field

import httpx

from app.core.config import settings

MAX_ATTEMPTS = 3
MAX_OUTPUT_TOKENS = 512
MAX_REQUEST_BYTES = 4096
RESERVATION_LIMIT = 16384
DEADLINE_SECONDS = 180
APPROVED_BENCHMARK_SHA256 = "2153e664f10f4cd0d412729ce842ab0165c8ed7b528500f2192c2f44d6ed379f"
demo_context = ContextVar("demo_context", default=None)
ledgers = {}


def bounded_demo():
    return settings.RESEARCH_DEMO_ENABLED or settings.RESEARCH_EVIDENCE_KIND == "provider_live"


class DemoBudgetError(RuntimeError):
    pass


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
    usage_complete: bool = True
    stopped: str | None = None

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
            reservationLimit=RESERVATION_LIMIT, reservationMeasurement="request bytes + output token cap; not tokenizer proof",
            providerReportedTokens=self.reported_tokens, usageComplete=self.usage_complete,
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
            if (request.method != "POST" or request.url.host != "api.groq.com"
                    or request.url.path != "/openai/v1/chat/completions"):
                raise DemoBudgetError("unapproved_provider_request")
            body = await request.aread()
            payload = json.loads(body)
            if (len(body) > MAX_REQUEST_BYTES or payload.get("max_tokens") != MAX_OUTPUT_TOKENS
                    or payload.get("stream", False) or payload.get("tools")):
                raise DemoBudgetError("request_budget_rejected")
            reservation = len(body) + MAX_OUTPUT_TOKENS
            # Reading a streamed body may yield. Recheck all shared state here.
            budget.check()
            if budget.reserved + reservation > RESERVATION_LIMIT:
                raise DemoBudgetError("reservation_budget_exhausted")
            # No await between shared checks and reservation: atomic in this event loop.
            budget.attempts += 1
            budget.reserved += reservation
            # Persist BEFORE network. A failed writer prevents the transport invocation.
            await self.evidence("attempt_reserved")
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
