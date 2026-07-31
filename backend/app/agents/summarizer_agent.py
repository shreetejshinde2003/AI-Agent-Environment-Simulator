"""
app/agents/summarizer_agent.py

RESERVED — one of the six agents. Fill in the `call_llm(...)` call
inside `process()` once app/agents/llm_client.py is activated.
"""

from app.agents.base_agent import BaseAgent

# USER-DEFINED: starting-point prompt — refine after real trials.
SYSTEM_PROMPT = """You are the Summarizer Agent in a multi-agent simulation.
You receive analysis/insights and condense them into a short, clear
summary suitable for a final report — a few sentences to a short
paragraph, no jargon, readable by someone who hasn't seen the raw data.
Hand off your summary to the Report Agent."""


class SummarizerAgent(BaseAgent):
    AGENT_ID = "summarizer"
    ROLE = "summarizer"
    MODEL = None  # None = use llm_client.DEFAULT_MODEL

    async def process(self, directive: str, context: dict):
        # RESERVED — uncomment once app/agents/llm_client.py is activated:
        #
        # from app.agents.llm_client import call_llm
        #
        # insights = context.get("insights", "")
        # response = await call_llm(
        #     prompt=f"Summarize these insights for a final report:\n\n{insights}",
        #     system=SYSTEM_PROMPT,
        #     model=self.MODEL,
        # )
        # return response   # return the LLMResponse object itself, not response.text — see research_agent.py
        raise NotImplementedError("SummarizerAgent.process() needs llm_client.py activated first")
