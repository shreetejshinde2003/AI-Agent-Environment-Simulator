"""Thin LangGraph node adapters around the existing executable agents.

These adapters deliberately do not own Task persistence, StageExecution
telemetry, WebSocket events, or handoff-message persistence. Those remain
with the existing task runtime until later LangGraph integration phases.
"""

from collections.abc import Awaitable, Callable
from typing import Protocol

from app.agents.analysis_agent import AnalysisAgent
from app.agents.contracts import CONTRACTS
from app.agents.data_agent import DataAgent
from app.agents.direct_agent import DirectAgent
from app.agents.execution_context import AgentId
from app.agents.graph_state import GraphRunState
from app.agents.report_agent import ReportAgent
from app.agents.research_agent import ResearchAgent
from app.agents.summarizer_agent import SummarizerAgent


class RunnableAgent(Protocol):
    async def run(self, directive: str, context) -> str: ...


AgentNode = Callable[[GraphRunState], Awaitable[dict]]


GRAPH_AGENTS: dict[AgentId, RunnableAgent] = {
    "research": ResearchAgent(),
    "data": DataAgent(),
    "analysis": AnalysisAgent(),
    "summarizer": SummarizerAgent(),
    "report": ReportAgent(),
    "direct": DirectAgent(),
}


def make_agent_node(
    agent_id: AgentId,
    *,
    agent: RunnableAgent | None = None,
) -> AgentNode:
    """Wrap one existing agent without duplicating its contract logic."""

    if agent_id not in CONTRACTS:
        raise ValueError(f"Unknown executable graph agent: {agent_id}")

    runnable = agent or GRAPH_AGENTS[agent_id]

    async def node(state: GraphRunState) -> dict:
        context = state["context"]

        if agent_id in state["completed_agents"]:
            raise ValueError(f"Graph agent '{agent_id}' has already completed.")

        result = await runnable.run(
            context.original_directive,
            context=context,
        )

        if not isinstance(result, str) or not result.strip():
            raise ValueError(f"Graph agent '{agent_id}' returned empty output.")

        next_context = context.with_output(agent_id, result)

        return {
            "context": next_context,
            "current_agent": agent_id,
            "completed_agents": (*state["completed_agents"], agent_id),
            "final_output": result,
        }

    return node


research_node = make_agent_node("research")
data_node = make_agent_node("data")
analysis_node = make_agent_node("analysis")
summarizer_node = make_agent_node("summarizer")
report_node = make_agent_node("report")
direct_node = make_agent_node("direct")


GRAPH_NODES: dict[AgentId, AgentNode] = {
    "research": research_node,
    "data": data_node,
    "analysis": analysis_node,
    "summarizer": summarizer_node,
    "report": report_node,
    "direct": direct_node,
}
