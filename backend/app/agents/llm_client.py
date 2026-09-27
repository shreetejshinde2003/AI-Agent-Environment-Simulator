"""
app/agents/llm_client.py

THE single place the LLM provider and model(s) get declared. Every
agent file in this folder calls `call_llm()` from here — no agent
should import the `groq` package (or any other provider SDK)
directly. That's what makes swapping models, or the provider itself,
later a one-file change instead of a hunt through six agent files.

--------------------------------------------------------------------
STATUS: ACTIVE — this makes real calls, using Groq's hosted API.
--------------------------------------------------------------------
Switched off local Ollama on 2026-09-25: Ollama only ran on one
teammate's laptop, so the deployed Railway backend could never reach
it ("Failed to connect to Ollama" in production was this, not a bug).
Groq was picked because it has a real no-credit-card free tier
(~30 req/min, OpenAI-compatible surface) — plenty for a classroom demo.

Needs GROQ_API_KEY set in the environment (get one at
console.groq.com/keys). Set it in backend/.env for local dev AND in
Railway's service → Variables tab for the deployed backend — .env is
gitignored, so Railway never sees it unless you add it there directly.

Verify DEFAULT_MODEL / FAST_MODEL below are still live model IDs at
console.groq.com/docs/models before relying on them — Groq deprecates
models over time (e.g. gemma2 was retired there already).

If the key is missing/invalid or the model ID is stale, `call_llm()`
will raise — that's the correct, honest failure mode (see
BaseAgent.run() / api/routes/tasks.py for how that gets surfaced to
the dashboard as a real error instead of hanging silently).

--------------------------------------------------------------------
SWITCHING PROVIDERS AGAIN LATER:
--------------------------------------------------------------------
Only this file changes. Keep the same `call_llm()` signature and
`LLMResponse` shape so none of the six agent files need to change.
The previous Ollama implementation and a commented-out Anthropic
version are both kept at the bottom of this file as references.
"""

import time
from dataclasses import dataclass

from groq import AsyncGroq

from app.core.config import settings

# ----------------------------------------------------------------------
# USER-DEFINED — model selection
# ----------------------------------------------------------------------
# Split reasoning-heavy agents (Research/Analysis/Report) from
# mechanical ones the same way you would with local model sizes —
# just picking two Groq model tiers instead of two pulled models.
DEFAULT_MODEL = settings.GROQ_MODEL       # <-- USER-DEFINED: reasoning-heavy agents — verify at console.groq.com/docs/models
FAST_MODEL = settings.GROQ_FAST_MODEL     # <-- USER-DEFINED: cheap/fast agents — verify at console.groq.com/docs/models

# USER-DEFINED: soft ceiling on response length per call — this DOES
# affect billing/free-tier token budget on a cloud provider, unlike
# with local Ollama, so don't raise it casually.
DEFAULT_MAX_TOKENS = 1024

_client = AsyncGroq(api_key=settings.GROQ_API_KEY)


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

    Token counts come from Groq's own `usage` block on the response,
    which mirrors OpenAI's chat-completions shape (prompt_tokens /
    completion_tokens) — real numbers, not guesses.
    """
    resolved_model = model or DEFAULT_MODEL
    start = time.perf_counter()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = await _client.chat.completions.create(
        model=resolved_model,
        messages=messages,
        max_tokens=max_tokens,
    )

    elapsed = time.perf_counter() - start
    usage = response.usage

    return LLMResponse(
        text=response.choices[0].message.content or "",
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        response_time_seconds=elapsed,
        model=resolved_model,
    )


# ----------------------------------------------------------------------
# RESERVED — previous local-Ollama implementation (not active). Kept as
# a reference in case the team ever needs to fall back to a local model
# (e.g. no internet at the venue, or free-tier limits get hit live).
# ----------------------------------------------------------------------
#
# from ollama import AsyncClient
# _ollama_client = AsyncClient(host=settings.OLLAMA_HOST)
#
# async def call_llm(prompt, system=None, model=None, max_tokens=DEFAULT_MAX_TOKENS) -> LLMResponse:
#     resolved_model = model or settings.OLLAMA_MODEL
#     start = time.perf_counter()
#     response = await _ollama_client.generate(
#         model=resolved_model,
#         prompt=prompt,
#         system=system or "",
#         options={"num_predict": max_tokens},
#     )
#     elapsed = time.perf_counter() - start
#     return LLMResponse(
#         text=response.get("response", ""),
#         input_tokens=response.get("prompt_eval_count", 0) or 0,
#         output_tokens=response.get("eval_count", 0) or 0,
#         response_time_seconds=elapsed,
#         model=resolved_model,
#     )


# ----------------------------------------------------------------------
# RESERVED — Anthropic alternate (not active). Swap to this
# implementation (keeping the function name/signature identical) if the
# team wants Claude's quality instead of Groq's speed later.
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
