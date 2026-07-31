"""
app/api/routes/agents.py

Endpoints for listing/creating agents and reading the relationship graph.

Currently backed by in-memory mock data so the frontend has something
real to point at before storage (app/storage/) or the agent framework
(app/agents/) exist. Swap `_MOCK_AGENTS` for a real DB query once
storage is activated — the response shape (schemas.Agent) does not
need to change.
"""

import uuid

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    Agent,
    AgentRelationship,
    AgentRuntimeStats,
    AgentStatus,
    CreateAgentRequest,
    RelationshipType,
)
from app.agents.stats_tracker import stats_tracker
from app.websocket.manager import manager

router = APIRouter(prefix="/agents", tags=["agents"])


# ----------------------------------------------------------------------
# Agent ROSTER — who exists and their display metadata (name/role/color).
# This is NOT their live status: `status` here is just the initial
# default. GET /agents (below) overrides it with the real, live status
# from app/agents/stats_tracker.py before returning — so a task
# actually has to run for an agent to show "active", instead of the
# roster claiming 6/7 agents are active when nothing has ever run.
# ----------------------------------------------------------------------
_MOCK_AGENTS: dict[str, Agent] = {
    "orchestrator": Agent(id="orchestrator", name="Orchestrator", role="orchestrator", status=AgentStatus.IDLE, color="#8b5cf6"),
    "research": Agent(id="research", name="Research Agent", role="research", status=AgentStatus.IDLE, color="#3b82f6"),
    "data": Agent(id="data", name="Data Agent", role="data", status=AgentStatus.IDLE, color="#22c55e"),
    "web_search": Agent(id="web_search", name="Web Search Agent", role="web_search", status=AgentStatus.IDLE, color="#f59e0b"),
    "analysis": Agent(id="analysis", name="Analysis Agent", role="analysis", status=AgentStatus.IDLE, color="#eab308"),
    "summarizer": Agent(id="summarizer", name="Summarizer Agent", role="summarizer", status=AgentStatus.IDLE, color="#14b8a6"),
    "report": Agent(id="report", name="Report Agent", role="report", status=AgentStatus.IDLE, color="#ec4899"),
}

_MOCK_RELATIONSHIPS: list[AgentRelationship] = [
    AgentRelationship(source_agent_id="orchestrator", target_agent_id="research", type=RelationshipType.DEPENDENCY, active=True),
    AgentRelationship(source_agent_id="orchestrator", target_agent_id="data", type=RelationshipType.DEPENDENCY, active=True),
    AgentRelationship(source_agent_id="orchestrator", target_agent_id="web_search", type=RelationshipType.DEPENDENCY, active=True),
    AgentRelationship(source_agent_id="orchestrator", target_agent_id="analysis", type=RelationshipType.DEPENDENCY, active=True),
    AgentRelationship(source_agent_id="orchestrator", target_agent_id="summarizer", type=RelationshipType.DEPENDENCY, active=True),
    AgentRelationship(source_agent_id="orchestrator", target_agent_id="report", type=RelationshipType.DEPENDENCY, active=False),
    AgentRelationship(source_agent_id="research", target_agent_id="data", type=RelationshipType.DATA_FLOW, active=True),
    AgentRelationship(source_agent_id="web_search", target_agent_id="orchestrator", type=RelationshipType.MESSAGE, active=True),
    AgentRelationship(source_agent_id="summarizer", target_agent_id="report", type=RelationshipType.DATA_FLOW, active=False),
]


@router.get("", response_model=list[Agent])
async def list_agents():
    """
    GET /api/v1/agents — powers the Agents page + graph node list.

    Merges each agent's REAL live status from stats_tracker (idle
    unless it's actually mid-call right now) into the static roster —
    the roster only supplies name/role/color, never status.
    """
    agents = []
    for agent in _MOCK_AGENTS.values():
        live_stats = stats_tracker.get(agent.id)
        live_status = live_stats.status if live_stats else agent.status
        agents.append(agent.model_copy(update={"status": live_status}))
    return agents


@router.get("/relationships", response_model=list[AgentRelationship])
async def list_agent_relationships():
    """GET /api/v1/agents/relationships — powers the Agent Relationship Graph edges."""
    return _MOCK_RELATIONSHIPS


@router.get("/stats", response_model=list[AgentRuntimeStats])
async def list_agent_stats():
    """
    GET /api/v1/agents/stats — powers the frontend's Agents page (token
    usage, avg response time, call counts per agent).

    IMPORTANT: this route MUST stay declared before GET /{agent_id}
    below — FastAPI matches routes in order, and /{agent_id} would
    otherwise swallow "/stats" as if "stats" were an agent id.

    Every value here comes straight from app/agents/stats_tracker.py,
    which starts every agent at a genuine zero and only updates once
    that agent's BaseAgent.run() actually executes a real LLM call
    (see app/agents/llm_client.py's activation checklist). Until then,
    this honestly returns all-zero stats — not fabricated numbers.
    """
    return stats_tracker.get_all()


@router.get("/{agent_id}/stats", response_model=AgentRuntimeStats)
async def get_agent_stats(agent_id: str):
    """GET /api/v1/agents/{id}/stats — one agent's real runtime stats."""
    stats = stats_tracker.get(agent_id)
    if stats is None:
        raise HTTPException(status_code=404, detail=f"No stats tracked for agent '{agent_id}'")
    return stats


@router.get("/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str):
    agent = _MOCK_AGENTS.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    live_stats = stats_tracker.get(agent_id)
    if live_stats:
        return agent.model_copy(update={"status": live_stats.status})
    return agent


@router.post("", response_model=Agent, status_code=201)
async def create_agent(payload: CreateAgentRequest):
    """POST /api/v1/agents — powers the 'Add Agent' quick action."""
    new_id = str(uuid.uuid4())[:8]
    agent = Agent(
        id=new_id,
        name=payload.name,
        role=payload.role,
        status=AgentStatus.IDLE,
        # USER-DEFINED: swap this for a real role->color lookup once
        # app/agents/ defines a fixed set of roles. Falls back to a
        # neutral gray if the caller doesn't provide one.
        color=payload.color or "#94a3b8",
    )
    _MOCK_AGENTS[new_id] = agent

    await manager.broadcast("agent_status_changed", agent.model_dump(mode="json"))
    return agent
