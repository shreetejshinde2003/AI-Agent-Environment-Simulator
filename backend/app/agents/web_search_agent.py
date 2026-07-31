"""
app/agents/web_search_agent.py

RESERVED — one of the six agents. Fill in the `call_llm(...)` call
inside `process()` once app/agents/llm_client.py is activated.
"""

from app.agents.base_agent import BaseAgent

# USER-DEFINED: starting-point prompt — refine after real trials.
SYSTEM_PROMPT = """You are the Web Search Agent in a multi-agent simulation.
Given a task directive, identify what should be searched for and
summarize what a real web search would need to return (competitor
websites, pricing pages, recent news). If you're given actual search
results as input (via a real search tool call — see the RESERVED note
below), summarize them factually instead of guessing."""


class WebSearchAgent(BaseAgent):
    AGENT_ID = "web_search"
    ROLE = "web_search"
    # USER-DEFINED: this agent's job is mostly mechanical retrieval +
    # light summarization — a strong example of where FAST_MODEL saves
    # real token cost across a long simulation without hurting quality.
    MODEL = None  # None = use llm_client.DEFAULT_MODEL — recommend llm_client.FAST_MODEL here after benchmarking

    async def process(self, directive: str, context: dict):
        # RESERVED — uncomment once app/agents/llm_client.py is activated:
        #
        # from app.agents.llm_client import call_llm, FAST_MODEL
        #
        # # RESERVED: for a REAL web search (not just an LLM guessing),
        # # wire in an actual search tool here (e.g. Anthropic's built-in
        # # web_search tool, or a SERP API) before calling the LLM to
        # # summarize the results. Passing the raw directive straight to
        # # the LLM without real search results risks the model
        # # fabricating sources — same failure mode the frontend was
        # # fixed for, just at the agent layer instead of the UI layer.
        # response = await call_llm(
        #     prompt=directive,
        #     system=SYSTEM_PROMPT,
        #     model=self.MODEL or FAST_MODEL,
        # )
        # return response   # return the LLMResponse object itself, not response.text — see research_agent.py
        raise NotImplementedError("WebSearchAgent.process() needs llm_client.py activated first")
