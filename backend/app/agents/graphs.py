"""Compiled LangGraph execution topologies.

These graphs orchestrate the canonical GraphRunState and existing agent-node
adapters. Task persistence, StageExecution lifecycle, events, messages,
evaluation, and WebSocket telemetry remain outside the graph at this phase.
"""

from langgraph.graph import END, START, StateGraph

from app.agents.graph_nodes import (
    AgentNode,
    analysis_node,
    data_node,
    direct_node,
    report_node,
    research_node,
    summarizer_node,
)
from app.agents.graph_state import GraphRunState
from app.agents.routing import SPECIALISTS


def build_single_graph(*, node: AgentNode = direct_node):
    """Compile the Single baseline topology: START -> direct -> END."""

    graph = StateGraph(GraphRunState)
    graph.add_node("direct", node)
    graph.add_edge(START, "direct")
    graph.add_edge("direct", END)
    return graph.compile()


single_graph = build_single_graph()


def build_fixed_graph(
    *,
    research: AgentNode = research_node,
    data: AgentNode = data_node,
    analysis: AgentNode = analysis_node,
    summarizer: AgentNode = summarizer_node,
    report: AgentNode = report_node,
):
    """Compile the Fixed five-stage topology used by the existing runtime."""

    graph = StateGraph(GraphRunState)

    graph.add_node("research", research)
    graph.add_node("data", data)
    graph.add_node("analysis", analysis)
    graph.add_node("summarizer", summarizer)
    graph.add_node("report", report)

    graph.add_edge(START, "research")
    graph.add_edge("research", "data")
    graph.add_edge("data", "analysis")
    graph.add_edge("analysis", "summarizer")
    graph.add_edge("summarizer", "report")
    graph.add_edge("report", END)

    return graph.compile()


fixed_graph = build_fixed_graph()



def _adaptive_next(state: GraphRunState):
    """Return the next persisted selected specialist, never make a route decision."""

    route = state["context"].route
    if route is None:
        raise ValueError("Adaptive graph requires a selected route.")

    selected = route.selected_agents
    skipped = route.skipped_agents

    if not selected:
        raise ValueError("Adaptive graph route cannot be empty.")

    if selected[-1] != "report":
        raise ValueError("Adaptive graph route must finish with report.")

    if selected != tuple(agent for agent in SPECIALISTS if agent in selected):
        raise ValueError("Adaptive graph route violates specialist order.")

    if skipped != tuple(agent for agent in SPECIALISTS if agent not in selected):
        raise ValueError("Adaptive graph selected/skipped agents do not form an exact partition.")

    completed = state["completed_agents"]

    if completed != selected[: len(completed)]:
        raise ValueError("Adaptive graph completed agents do not match the selected route prefix.")

    if len(completed) == len(selected):
        return END

    return selected[len(completed)]


def build_adaptive_graph(
    *,
    research: AgentNode = research_node,
    data: AgentNode = data_node,
    analysis: AgentNode = analysis_node,
    summarizer: AgentNode = summarizer_node,
    report: AgentNode = report_node,
):
    """Compile execution over an already-selected Adaptive specialist route."""

    graph = StateGraph(GraphRunState)

    graph.add_node("research", research)
    graph.add_node("data", data)
    graph.add_node("analysis", analysis)
    graph.add_node("summarizer", summarizer)
    graph.add_node("report", report)

    destinations = {
        "research": "research",
        "data": "data",
        "analysis": "analysis",
        "summarizer": "summarizer",
        "report": "report",
        END: END,
    }

    graph.add_conditional_edges(START, _adaptive_next, destinations)

    for agent_id in SPECIALISTS:
        graph.add_conditional_edges(agent_id, _adaptive_next, destinations)

    return graph.compile()


adaptive_graph = build_adaptive_graph()
