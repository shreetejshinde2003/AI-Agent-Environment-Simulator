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
  the actual `call_llm(...)` call goes. Five agents implement it;
  Web Search intentionally remains unavailable.
"""

import time

from app.agents.stats_tracker import stats_tracker
from app.agents.llm_client import DEFAULT_MODEL
from app.models.schemas import AgentStatus
from app.agents.execution_context import ExecutionContext, current_execution


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

    async def process(self, directive: str, context: ExecutionContext | dict):
        """
        Executable agent subclasses override this. Call `app.agents.llm_client.call_llm(...)`
        and return the resulting LLMResponse object directly (not just
        the text) — see research_agent.py for the working example.
        Left unimplemented here on purpose.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.process() is not implemented yet — "
            f"provide an executable process() implementation."
        )

    async def run(self, directive: str, context: ExecutionContext | dict | None = None) -> str:
        """
        Public entrypoint — the orchestrator calls THIS, not process().
        Times the call and reports real stats to stats_tracker
        regardless of which agent subclass is running.
        """
        context = {} if context is None else context
        stats_tracker.set_status(self.AGENT_ID, AgentStatus.ACTIVE)
        start = time.perf_counter()

        try:
            result = await self.process(directive, context)
        except Exception:
            stats_tracker.set_status(self.AGENT_ID, AgentStatus.ERROR)
            raise

        elapsed = time.perf_counter() - start
        execution = current_execution.get()
        if execution is not None and hasattr(result, "total_tokens"):
            execution.model = result.model
            execution.input_tokens = result.input_tokens
            execution.output_tokens = result.output_tokens
            execution.total_tokens = result.total_tokens

        # Implemented agents return LLMResponse with provider usage.
        # The request-local stage captures these metrics independently
        # of global counters, including simultaneous runs.
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

        if execution is not None and self.AGENT_ID in {"research", "data", "analysis", "summarizer", "report", "direct"}:
            from app.agents.output_contract import validate_output
            terminal = (self.AGENT_ID in {"report", "direct"} or
                        isinstance(context, ExecutionContext) and (
                            context.execution_mode.value == "single_agent" or
                            context.route and context.route.selected_agents[-1] == self.AGENT_ID))
            if terminal:
                execution.output_contract = validate_output(text, directive)

        stats_tracker.record_call(
            agent_id=self.AGENT_ID,
            response_time_seconds=elapsed,
            tokens_used=tokens_used,
            response_preview=text,
            model_used=model_used,
        )
        stats_tracker.set_status(self.AGENT_ID, AgentStatus.IDLE)
        return text
