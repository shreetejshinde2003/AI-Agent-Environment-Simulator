"""
app/agents/research_agent.py

RESERVED — one of the six agents. Fill in the `call_llm(...)` call
inside `process()` once app/agents/llm_client.py is activated.
"""

from app.agents.base_agent import BaseAgent
from app.agents.llm_client import call_llm
# USER-DEFINED: starting-point prompt — refine once you've picked the
# LLM and run a few real trials against actual task directives.
SYSTEM_PROMPT = """You are the Research Agent in a multi-agent simulation.
Given a task directive, gather relevant information (market data,
competitor details, background facts — whatever the directive calls
for) and hand off structured findings for the Data Agent to process.
Be concise. Note where each piece of information came from."""


class ResearchAgent(BaseAgent):
    AGENT_ID = "research"
    ROLE = "research"
    # USER-DEFINED: research is open-ended reasoning — worth the
    # stronger default model rather than the FAST_MODEL used by more
    # mechanical agents (see web_search_agent.py for that comparison).
    MODEL = None  # None = use llm_client.DEFAULT_MODEL

    async def process(self, directive: str, context: dict) -> str:

        response = await call_llm(
            prompt=directive,
            system=SYSTEM_PROMPT,
            model=self.MODEL,
        )

        return response.text