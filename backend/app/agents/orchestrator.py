"""
app/agents/orchestrator.py

RESERVED for Member C — this is where the actual LangGraph multi-agent
graph lives once the framework prototype (see the standalone research
spike outside this repo) is validated and ready to integrate.

--------------------------------------------------------------------
WHAT GOES HERE EVENTUALLY:
--------------------------------------------------------------------
1. Agent node functions (one per agent role: research, data, web_search,
   analysis, summarizer, report — matching app/models/schemas.py's
   `Agent.role` values so the frontend graph coloring lines up for free).
2. A LangGraph StateGraph wiring those nodes together with conditional
   edges (the "Agent Relationship Graph" the frontend renders is
   literally a visualization of this graph — keep node names consistent
   with Agent.id values used elsewhere).
3. A checkpointer (LangGraph's built-in state persistence) — this is
   what powers "Replay Mode" on the frontend, so don't skip it even in
   the prototype phase.
4. A function like `run_simulation(goal: str) -> AsyncIterator[dict]`
   that the API route in app/api/routes/simulation.py will call, and
   that pushes updates through `app/websocket/manager.py.broadcast(...)`
   as the graph executes.

--------------------------------------------------------------------
USER-DEFINED when this gets built:
--------------------------------------------------------------------
- LLM provider + model name per node (some nodes may use a cheaper/
  faster model than others — this is a real token-cost decision, not
  just a config detail).
- ANTHROPIC_API_KEY / OPENAI_API_KEY — read from app.core.config.settings,
  never hardcoded here.
- Max recursion depth / task budget (see the "Recursion depth control"
  trade-off in Project3_TechStack_and_FileStructure.md, Section on Key
  Design Decisions) — LangGraph will loop forever without this.

--------------------------------------------------------------------
Example shape (uncomment and adapt once langgraph is added to
requirements.txt):
--------------------------------------------------------------------
"""

# from langgraph.graph import StateGraph, END
# from langgraph.checkpoint.memory import MemorySaver
# from typing import TypedDict, Annotated
# import operator
#
# from app.core.config import settings  # <-- USER-DEFINED: API keys live here, not inline
#
#
# class SimulationState(TypedDict):
#     goal: str
#     messages: Annotated[list, operator.add]
#     # RESERVED: add whatever shared state the agents actually need
#     # (e.g. research_findings, draft_report, iteration_count)
#
#
# def research_node(state: SimulationState) -> SimulationState:
#     # TODO(Member C): call the LLM, update state, broadcast progress
#     raise NotImplementedError
#
#
# def build_graph() -> StateGraph:
#     graph = StateGraph(SimulationState)
#     graph.add_node("research", research_node)
#     # graph.add_node(...)  # one per agent role
#     # graph.add_edge(...)  # wire up the relationships
#     graph.set_entry_point("research")
#     return graph.compile(checkpointer=MemorySaver())
#
#
# async def run_simulation(goal: str):
#     """Called by app/api/routes/simulation.py. Yields state updates as
#     the graph executes, which the route forwards to the WebSocket
#     manager for the live dashboard."""
#     raise NotImplementedError
