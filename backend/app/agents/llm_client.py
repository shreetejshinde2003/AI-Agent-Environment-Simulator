"""
app/agents/llm_client.py

THE single place the LLM provider and model(s) get declared. Every
agent file in this folder calls `call_llm()` from here — no agent
should import the `ollama` package (or any other provider SDK)
directly. That's what makes swapping models, or the provider itself,
later a one-file change instead of a hunt through six agent files.

--------------------------------------------------------------------
STATUS: ACTIVE — this makes real calls, using Ollama.
--------------------------------------------------------------------
Matches the team's already-validated setup: a local Ollama server
running gemma2:2b. Before this will work, you need Ollama actually
running with the model pulled:

    ollama serve             # in its own terminal, leave it running
    ollama pull gemma2:2b     # one-time — confirm with `ollama list`

If Ollama isn't running, `call_llm()` will raise a connection error —
that's the correct, honest failure mode (see BaseAgent.run() /
api/routes/tasks.py for how that gets surfaced to the dashboard as a
real error instead of hanging silently).

--------------------------------------------------------------------
SWITCHING PROVIDERS LATER (e.g. to Claude/GPT for better quality):
--------------------------------------------------------------------
Only this file changes. Keep the same `call_llm()` signature and
`LLMResponse` shape so none of the six agent files need to change.
A commented-out Anthropic version is included at the bottom of this
file as a starting point when that day comes.
"""

import time
from dataclasses import dataclass

from ollama import AsyncClient

from app.core.config import settings

# ----------------------------------------------------------------------
# USER-DEFINED — model selection
# ----------------------------------------------------------------------
# Both point at the same local model today, since the team is running
# one model. Split these the same way cloud setups split a
# reasoning-heavy default from a cheap/fast option once you're running
# more than one local model size (e.g. gemma2:2b for mechanical agents,
# a larger model for Research/Analysis/Report).
DEFAULT_MODEL = settings.OLLAMA_MODEL   # <-- USER-DEFINED: reasoning-heavy agents
FAST_MODEL = settings.OLLAMA_MODEL       # <-- USER-DEFINED: point at a smaller/faster model once you have one pulled

# USER-DEFINED: soft ceiling on response length per call (Ollama's
# `num_predict` option) — prevents one runaway response from eating the
# whole simulation's time budget. Unlike cloud APIs this doesn't affect
# billing, but it does affect how long you wait.
DEFAULT_MAX_TOKENS = 1024

_client = AsyncClient(host=settings.OLLAMA_HOST)


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


async def call_llm(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> LLMResponse:
    """
    The ONE function every agent calls to talk to the LLM. Wraps timing
    so callers (BaseAgent.run(), via stats_tracker) get real
    response-time numbers — not estimates.

    Token counts come from Ollama's own response fields
    (`prompt_eval_count` / `eval_count`), which are Ollama's equivalent
    of input/output tokens — real numbers, not guesses.
    """
    resolved_model = model or DEFAULT_MODEL
    start = time.perf_counter()

    response = await _client.generate(
        model=resolved_model,
        prompt=prompt,
        system=system or "",
        options={"num_predict": max_tokens},
    )

    elapsed = time.perf_counter() - start

    return LLMResponse(
        text=response.get("response", ""),
        input_tokens=response.get("prompt_eval_count", 0) or 0,
        output_tokens=response.get("eval_count", 0) or 0,
        response_time_seconds=elapsed,
        model=resolved_model,
    )


# ----------------------------------------------------------------------
# RESERVED — cloud provider alternate (not active). Swap to this
# implementation (keeping the function name/signature identical) if the
# team moves off a local model later.
# ----------------------------------------------------------------------
#
# from anthropic import Anthropic
#
# _cloud_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
#
# async def call_llm(prompt, system=None, model=None, max_tokens=DEFAULT_MAX_TOKENS) -> LLMResponse:
#     resolved_model = model or "claude-sonnet-4-5"
#     start = time.perf_counter()
#     response = _cloud_client.messages.create(
#         model=resolved_model,
#         max_tokens=max_tokens,
#         system=system or "",
#         messages=[{"role": "user", "content": prompt}],
#     )
#     elapsed = time.perf_counter() - start
#     text = "".join(block.text for block in response.content if block.type == "text")
#     return LLMResponse(
#         text=text,
#         input_tokens=response.usage.input_tokens,
#         output_tokens=response.usage.output_tokens,
#         response_time_seconds=elapsed,
#         model=resolved_model,
#     )
