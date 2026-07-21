"""
app/agents/web_search_agent.py

RESERVED — one of the six agents. Fill in the `call_llm(...)` call
inside `process()` once app/agents/llm_client.py is activated.
"""

from multiprocessing import context
from urllib import response

from app.agents.base_agent import BaseAgent
from backend.app.agents.llm_client_backup import call_llm

# USER-DEFINED: starting-point prompt — refine after real trials.
SYSTEM_PROMPT = """You are the Web Search Agent in a multi-agent simulation.
Given a task directive, identify what should be searched for and
summarize what a real web search would need to return (competitor
websites, pricing pages, recent news). If you're given actual search
results as input (via a real search tool call — see the RESERVED note
below), summarize them factually instead of guessing.
Your responsibility is to identify information that should be gathered
from external sources.

Rules:

- Focus on identifying missing or outdated information.
- Suggest useful search queries.
- Do not fabricate web results.
- If no external search is needed, explicitly state that.
- Return Markdown."""


class WebSearchAgent(BaseAgent):
    AGENT_ID = "web_search"
    ROLE = "web_search"
    # USER-DEFINED: this agent's job is mostly mechanical retrieval +
    # light summarization — a strong example of where FAST_MODEL saves
    # real token cost across a long simulation without hurting quality.
    MODEL = None  # None = use llm_client.DEFAULT_MODEL — recommend llm_client.FAST_MODEL here after benchmarking

    async def process(self, directive: str, context: dict) -> str:

        research_findings = context.get("research_findings", "")

        prompt = f"""
Task:
{directive}

Current Research:
{research_findings}

Determine whether additional web searches are required.
If yes, suggest search queries.
"""

        response = await call_llm(
        prompt=prompt,
        system=SYSTEM_PROMPT,
        model=self.MODEL,
    )

        return response.text