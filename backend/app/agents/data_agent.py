"""
app/agents/data_agent.py

RESERVED — one of the six agents. Fill in the `call_llm(...)` call
inside `process()` once app/agents/llm_client.py is activated.
"""

from app.agents.base_agent import BaseAgent

# USER-DEFINED: starting-point prompt — refine after real trials.
SYSTEM_PROMPT = """You are the Data Agent in a multi-agent simulation.
You receive raw findings from the Research Agent and structure them
into clean, well-labeled records (e.g. a table of competitors with
fields for name, pricing, key features). Output structured data the
Analysis Agent can reason over directly — prefer a consistent format
(e.g. one JSON object per record) over free-form prose."""


class DataAgent(BaseAgent):
    AGENT_ID = "data"
    ROLE = "data"
    # USER-DEFINED: structuring/extraction is fairly mechanical — the
    # FAST_MODEL is likely sufficient here. Benchmark before assuming;
    # if outputs are unreliable, bump back to DEFAULT_MODEL.
    MODEL = None  # None = use llm_client.DEFAULT_MODEL — swap to FAST_MODEL after benchmarking

    async def process(self, directive: str, context: dict):
        # `context` should include the Research Agent's output by the
        # time the orchestrator calls this agent — see
        # app/agents/orchestrator.py's SimulationState design.
        from app.agents.llm_client import call_llm

        research_findings = context.get("research_findings", "")
        response = await call_llm(
            prompt=f"Structure this research into clean records:\n\n{research_findings}",
            system=SYSTEM_PROMPT,
            model=self.MODEL,
        )
        return response  # return the LLMResponse object itself, not response.text — see research_agent.py
