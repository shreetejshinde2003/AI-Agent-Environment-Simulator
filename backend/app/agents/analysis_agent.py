"""
app/agents/analysis_agent.py

RESERVED — one of the six agents. Fill in the `call_llm(...)` call
inside `process()` once app/agents/llm_client.py is activated.
"""

from app.agents.base_agent import BaseAgent

# USER-DEFINED: starting-point prompt — refine after real trials.
SYSTEM_PROMPT = """You are the Analysis Agent in a multi-agent simulation.
You receive structured data from the Data Agent and produce insights:
patterns, comparisons, notable outliers, and a short recommendation.
Be specific — reference the actual data points you're reasoning about,
don't generalize. Hand off your insights for the Summarizer Agent."""


class AnalysisAgent(BaseAgent):
    AGENT_ID = "analysis"
    ROLE = "analysis"
    # USER-DEFINED: reasoning over structured data to find patterns is
    # exactly the kind of task where a stronger model earns its cost.
    MODEL = None  # None = use llm_client.DEFAULT_MODEL

    async def process(self, directive: str, context: dict) -> str:
        # RESERVED — uncomment once app/agents/llm_client.py is activated:
        #
        # from app.agents.llm_client import call_llm
        #
        # structured_data = context.get("structured_data", "")
        # response = await call_llm(
        #     prompt=f"Analyze this data and produce insights:\n\n{structured_data}",
        #     system=SYSTEM_PROMPT,
        #     model=self.MODEL,
        # )
        # return response.text
        raise NotImplementedError("AnalysisAgent.process() needs llm_client.py activated first")
