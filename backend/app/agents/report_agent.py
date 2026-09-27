"""
app/agents/report_agent.py

RESERVED — one of the six agents. Fill in the `call_llm(...)` call
inside `process()` once app/agents/llm_client.py is activated.
"""

from app.agents.base_agent import BaseAgent

# USER-DEFINED: starting-point prompt — refine after real trials.
SYSTEM_PROMPT = """You are the Report Agent in a multi-agent simulation.
You receive a summary and produce the final, formatted output for the
end user — headings, structure, and a clear conclusion. This is the
last agent in the chain; your output is what the user actually reads,
so prioritize clarity and completeness over brevity."""


class ReportAgent(BaseAgent):
    AGENT_ID = "report"
    ROLE = "report"
    # USER-DEFINED: final formatting/writing quality matters most here
    # since this is what the end user actually sees — default to the
    # stronger model.
    MODEL = None  # None = use llm_client.DEFAULT_MODEL

    async def process(self, directive: str, context: dict):
        # RESERVED — uncomment once app/agents/llm_client.py is activated:
        #
        from app.agents.llm_client import call_llm
        #
        summary = context.get("summary", "")
        response = await call_llm(
            prompt=f"Write the final report based on this summary:\n\n{summary}",
            system=SYSTEM_PROMPT,
            model=self.MODEL,
        )
        return response  # return the LLMResponse object itself, not response.text — see research_agent.py
