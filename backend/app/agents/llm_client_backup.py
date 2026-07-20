"""
app/agents/llm_client.py

THE single place the LLM provider and model(s) get declared. Every
agent file in this folder should call `call_llm()` from here — no
agent should import an LLM SDK directly. That's what makes swapping
providers later (or using a different model per agent) a one-file change.

--------------------------------------------------------------------
STATUS: RESERVED — no real API calls happen yet.
--------------------------------------------------------------------
Calling `call_llm()` right now raises NotImplementedError on purpose.
A stub that returned canned text would silently reintroduce the exact
"fabricated data" problem the frontend was fixed for — an agent
"responding" with fake text is worse than an agent that clearly
doesn't work yet. See the checklist below to activate it for real.

--------------------------------------------------------------------
HOW TO ACTIVATE THIS (checklist):
--------------------------------------------------------------------
1. `pip install anthropic` (already in requirements.txt, commented out
   — uncomment it) and set ANTHROPIC_API_KEY in your .env.
2. Uncomment the `_client = Anthropic(...)` line and the real body of
   `call_llm()` below.
3. Each of the six agent files (research_agent.py, data_agent.py, etc.)
   already has a commented-out call to `call_llm(...)` in its
   `process()` method — uncomment those once this file is live.
4. Token usage: Anthropic's response includes `usage.input_tokens` /
   `usage.output_tokens` — wire those into the LLMResponse below so
   app/agents/stats_tracker.py reports REAL token counts, not zeros.
"""

import time
from dataclasses import dataclass

from app.core.config import settings

# ----------------------------------------------------------------------
# USER-DEFINED — model selection
# ----------------------------------------------------------------------
# Pick models based on what each agent actually needs. Research/Analysis/
# Summarizer are open-ended reasoning tasks — worth a stronger model.
# Web Search/Data extraction are more mechanical — a cheaper/faster
# model is usually fine and meaningfully reduces token cost across a
# long simulation. This split is a real cost decision, not a detail —
# see the "Research Paper Track" trade-off notes in the project's
# tech-stack doc for why this matters at simulation scale.
DEFAULT_MODEL = "claude-sonnet-4-5"   # <-- USER-DEFINED: reasoning-heavy agents
FAST_MODEL = "claude-haiku-4-5"        # <-- USER-DEFINED: mechanical/high-volume agents

# USER-DEFINED: hard ceiling per call — prevents one runaway agent
# response from blowing the token budget for the whole simulation.
DEFAULT_MAX_TOKENS = 1024


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    response_time_seconds: float
    model: str

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# RESERVED — uncomment once ready to make real calls:
#
# from anthropic import Anthropic
#
# _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)  # <-- USER-DEFINED: key lives in .env, see app/core/config.py
#
# async def call_llm(
#     prompt: str,
#     system: str | None = None,
#     model: str | None = None,
#     max_tokens: int = DEFAULT_MAX_TOKENS,
# ) -> LLMResponse:
#     """
#     The ONE function every agent calls to talk to an LLM. Wraps
#     timing so callers (BaseAgent.run(), via stats_tracker) get real
#     response-time numbers, not guesses.
#     """
#     resolved_model = model or DEFAULT_MODEL
#     start = time.perf_counter()
#
#     response = _client.messages.create(
#         model=resolved_model,
#         max_tokens=max_tokens,
#         system=system or "",
#         messages=[{"role": "user", "content": prompt}],
#     )
#
#     elapsed = time.perf_counter() - start
#     text = "".join(block.text for block in response.content if block.type == "text")
#
#     return LLMResponse(
#         text=text,
#         input_tokens=response.usage.input_tokens,
#         output_tokens=response.usage.output_tokens,
#         response_time_seconds=elapsed,
#         model=resolved_model,
#     )


async def call_llm(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> LLMResponse:
    """
    RESERVED — replace this whole function body with the real
    implementation above once the checklist at the top of this file is
    done. Raising here (instead of returning fake text) is
    intentional — see the module docstring.
    """
    raise NotImplementedError(
        "call_llm() is not wired up yet — see the activation checklist "
        "at the top of app/agents/llm_client.py"
    )
