"""
app/agents/research_agent.py

ACTIVE — the first of the six agents to actually call the LLM.
Matches the team's already-validated setup: given a task directive,
this calls Ollama (gemma2:2b) and returns real research findings.

The other five agent files in this folder are still RESERVED
(NotImplementedError) — this one is the template for bringing them
online the same way, once Research is confirmed working end to end.
"""

from app.agents.base_agent import BaseAgent
from app.agents.llm_client import call_llm

# USER-DEFINED: refine this prompt based on real output quality —
# gemma2:2b is a small model, so being explicit about the expected
# format (headings, sourcing caveats) measurably helps output quality.
SYSTEM_PROMPT = """You are the Research Agent in a multi-agent simulation.
Given a task directive, gather relevant information and present it as
clear, structured findings (use headings and bullet points). Note
plainly that you are a local language model without live internet
access, so any facts you state should be flagged as your own knowledge,
not a live search result. Keep the response focused and readable."""


class ResearchAgent(BaseAgent):
    AGENT_ID = "research"
    ROLE = "research"
    # USER-DEFINED: research is open-ended reasoning — if you later pull
    # a larger local model, point this agent at it instead of FAST_MODEL.
    MODEL = None  # None = use llm_client.DEFAULT_MODEL

    async def process(self, directive: str, context: dict):
        # Returns the LLMResponse object itself (not just .text) — see
        # BaseAgent.run(), which extracts real token counts from it for
        # stats_tracker. Agents still RESERVED (raising
        # NotImplementedError) never reach this point.
        return await call_llm(
            prompt=directive,
            system=SYSTEM_PROMPT,
            model=self.MODEL,
        )
