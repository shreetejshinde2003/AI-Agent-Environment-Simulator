"""
app/agents/base_agent.py

Shared base class every one of the six agents inherits from. Handles
the bookkeeping — timing each call, reporting stats to
app/agents/stats_tracker.py — so each individual agent file only has
to define its role, its system prompt, and what it asks the LLM to do.

--------------------------------------------------------------------
IMPORTANT — the split between run() and process():
--------------------------------------------------------------------
- `run()` is the public entrypoint the orchestrator calls. It wraps
  process() with timing + stats capture. DO NOT override this in a
  subclass.
- `process()` is what each agent subclass implements — this is where
  the actual `call_llm(...)` call goes. RESERVED (raises
  NotImplementedError) in every agent file until llm_client.py is
  activated.
"""

import time

from app.agents.stats_tracker import stats_tracker
from app.agents.llm_client import DEFAULT_MODEL
from app.models.schemas import AgentStatus


class BaseAgent:
    # USER-DEFINED: every subclass must override these two.
    AGENT_ID: str = "base"       # must match an id in stats_tracker.KNOWN_AGENT_IDS
    ROLE: str = "base"

    # USER-DEFINED: override per-agent if this agent should use a
    # different model than the default (see llm_client.py's
    # DEFAULT_MODEL / FAST_MODEL split). None = use the default.
    MODEL: str | None = None

    def __init__(self) -> None:
        stats_tracker.register(self.AGENT_ID)

    async def process(self, directive: str, context: dict):
        """
        RESERVED (for 5 of the 6 agents) — every agent subclass
        overrides this. Should call `app.agents.llm_client.call_llm(...)`
        and return the resulting LLMResponse object directly (not just
        the text) — see research_agent.py for the working example.
        Left unimplemented here on purpose.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.process() is not implemented yet — "
            f"see the RESERVED block inside it."
        )

    async def run(self, directive: str, context: dict | None = None) -> str:
        """
        Public entrypoint — the orchestrator calls THIS, not process().
        Times the call and reports real stats to stats_tracker
        regardless of which agent subclass is running.
        """
        context = context or {}
        stats_tracker.set_status(self.AGENT_ID, AgentStatus.ACTIVE)
        start = time.perf_counter()

        try:
            result = await self.process(directive, context)
        except Exception:
            stats_tracker.set_status(self.AGENT_ID, AgentStatus.ERROR)
            raise

        elapsed = time.perf_counter() - start

        # Agents that call a real LLM (research_agent.py) return the
        # LLMResponse object directly, so we get genuine token counts.
        # Agents still RESERVED raise NotImplementedError above and
        # never reach this line, so there's no risk of this silently
        # reporting fake numbers for an agent that didn't really run.
        if hasattr(result, "text") and hasattr(result, "total_tokens"):
            text = result.text
            tokens_used = result.total_tokens
            model_used = result.model
        else:
            # Defensive fallback only — in practice every agent either
            # returns an LLMResponse or raises before getting here.
            text = result
            tokens_used = 0
            model_used = self.MODEL or DEFAULT_MODEL

        stats_tracker.record_call(
            agent_id=self.AGENT_ID,
            response_time_seconds=elapsed,
            tokens_used=tokens_used,
            response_preview=text,
            model_used=model_used,
        )
        stats_tracker.set_status(self.AGENT_ID, AgentStatus.IDLE)
        return text
