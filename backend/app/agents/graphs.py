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
