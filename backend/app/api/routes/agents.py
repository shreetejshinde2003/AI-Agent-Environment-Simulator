"""Agent roster and persistent execution statistics; metadata is not an implementation."""
from fastapi import APIRouter, Header, HTTPException, Request
from app.models.schemas import Agent, AgentRelationship, AgentRuntimeStats, AgentStatus
from app.storage.database import repository
from app.api.routes.workspaces import require_request_permission, request_user_id
from app.security.rbac import Permission

router = APIRouter(prefix="/agents", tags=["agents"])
_ROSTER = [
    ("orchestrator", "Orchestrator", "#8b5cf6"),
    ("research", "Research Agent", "#3b82f6"), ("data", "Data Agent", "#22c55e"),
    ("analysis", "Analysis Agent", "#eab308"), ("summarizer", "Summarizer Agent", "#14b8a6"),
    ("report", "Report Agent", "#ec4899"), ("direct", "Direct Agent", "#60a5fa"),
    ("web_search", "Web Search Agent", "#f59e0b"),
]
EXECUTABLE = {"research", "data", "analysis", "summarizer", "report", "direct"}


def _workspace_runs(request: Request, workspace_id: str | None):
    workspace = require_request_permission(request, workspace_id, Permission.SIMULATION_VIEW)
    return repository.list_for_tenant(
        workspace_id=workspace["id"], user_id=request_user_id(request)
    )

@router.get("", response_model=list[Agent])
async def list_agents(request: Request, x_workspace_id: str | None = Header(default=None)):
    active = {s.agent_id for r in _workspace_runs(request, x_workspace_id)
              for s in r.stages if s.status == "active"}
    agents = [Agent(id=aid, name=name, role=aid, color=color,
                    status=AgentStatus.ACTIVE if aid in active else AgentStatus.IDLE,
                    implemented=aid in EXECUTABLE) for aid, name, color in _ROSTER]
    return agents + [Agent.model_validate(a) for a in repository.agents()]

@router.get("/relationships", response_model=list[AgentRelationship])
async def list_agent_relationships():
    sequence = ["orchestrator", "research", "data", "analysis", "summarizer", "report"]
    return [AgentRelationship(source_agent_id=a, target_agent_id=b, type="data_flow")
            for a, b in zip(sequence, sequence[1:])]

@router.get("/stats", response_model=list[AgentRuntimeStats])
async def list_agent_stats(request: Request, x_workspace_id: str | None = Header(default=None)):
    runs = _workspace_runs(request, x_workspace_id)
    result = []
    for aid, _, _ in _ROSTER:
        stages = [s for r in runs for s in r.stages if s.agent_id == aid and s.started_at]
        times = [s.duration_seconds for s in stages if s.duration_seconds is not None]
        last = max(stages, key=lambda s: s.started_at) if stages else None
        result.append(AgentRuntimeStats(
            agent_id=aid, status="active" if any(s.status == "active" for s in stages) else
            "error" if last and last.status == "failed" else "idle",
            calls_made=len(stages), total_tokens_used=sum(s.total_tokens or 0 for s in stages),
            avg_response_time_seconds=sum(times)/len(times) if times else 0,
            last_response_time_seconds=last.duration_seconds if last else None,
            last_response_preview=(last.output or "")[:200] if last else None,
            last_called_at=last.started_at if last else None, model_used=last.model if last else None))
    return result

@router.get("/{agent_id}/stats", response_model=AgentRuntimeStats)
async def get_agent_stats(agent_id: str, request: Request, x_workspace_id: str | None = Header(default=None)):
    result = next((s for s in await list_agent_stats(request, x_workspace_id) if s.agent_id == agent_id), None)
    if result is None:
        raise HTTPException(404, "Agent not found")
    return result

@router.get("/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str, request: Request, x_workspace_id: str | None = Header(default=None)):
    result = next((a for a in await list_agents(request, x_workspace_id) if a.id == agent_id), None)
    if result is None:
        raise HTTPException(404, "Agent not found")
    return result

@router.post("", status_code=410)
async def create_agent(request: Request, x_workspace_id: str | None = Header(default=None)):
    require_request_permission(request, x_workspace_id, Permission.AGENT_MANAGE)
    raise HTTPException(410, detail={"code": "use_agent_builder", "message": "Create executable agents through /agent-builder."})
