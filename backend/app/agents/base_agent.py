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

    async def process(self, directive: str, context: dict) -> str:
        """
        RESERVED — every agent subclass overrides this. Should call
        `app.agents.llm_client.call_llm(...)` and return the response
        text. Left unimplemented here on purpose — see the six agent
        files in this folder for where this gets filled in.
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
        start = time.perf_counter()

        result_text = await self.process(directive, context)

        elapsed = time.perf_counter() - start
        # RESERVED: token counts should come from the real LLM response
        # (see llm_client.LLMResponse.total_tokens) once process() is
        # implemented and returns that alongside the text — 0 here is
        # the honest value for a call that didn't happen, not a filler
        # guess. Update this once process() returns real usage data.
        stats_tracker.record_call(
            agent_id=self.AGENT_ID,
            response_time_seconds=elapsed,
            tokens_used=0,
            response_preview=result_text,
            model_used=self.MODEL or DEFAULT_MODEL,
        )
        return result_text
