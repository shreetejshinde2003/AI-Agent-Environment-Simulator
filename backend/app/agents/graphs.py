"""Compiled LangGraph execution topologies.

These graphs orchestrate the canonical GraphRunState and existing agent-node
adapters. Task persistence, StageExecution lifecycle, events, messages,
evaluation, and WebSocket telemetry remain outside the graph at this phase.
"""

from langgraph.graph import END, START, StateGraph

from app.agents.graph_nodes import AgentNode, direct_node
from app.agents.graph_state import GraphRunState


def build_single_graph(*, node: AgentNode = direct_node):
    """Compile the Single baseline topology: START -> direct -> END."""

    graph = StateGraph(GraphRunState)
    graph.add_node("direct", node)
    graph.add_edge(START, "direct")
    graph.add_edge("direct", END)
    return graph.compile()


single_graph = build_single_graph()
