"""
app/api/routes/simulation.py

Top-level simulation control + stats — powers the stat-card row
(Agents Active, Tasks Completed, Messages, Avg Response Time, Success
Rate), the Activity Feed, and the Topbar's Replay/Pause/Stop controls.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.models.schemas import ActivityEvent, SimulationStats, SimulationStatus
from app.websocket.manager import manager

router = APIRouter(prefix="/simulation", tags=["simulation"])


# ----------------------------------------------------------------------
# TEMPORARY in-memory mock state — replace with real orchestrator state
# once app/agents/orchestrator.py is wired up (that's the actual source
# of truth for "is the simulation running", not this dict).
# ----------------------------------------------------------------------
_MOCK_STATS = SimulationStats(
    simulation_id="SIM-2024-05-12-001",
    status=SimulationStatus.RUNNING,
    start_time=datetime.now(timezone.utc),
    duration_seconds=765,
    total_agents=7,
    active_agents=6,
    total_tasks=28,
    completed_tasks=17,
    total_messages=142,
    avg_response_time_seconds=2.34,
    success_rate_percent=95.2,
)

_MOCK_ACTIVITY: list[ActivityEvent] = [
    ActivityEvent(id="a1", agent_id="analysis", text="completed data analysis", timestamp=datetime.now(timezone.utc)),
    ActivityEvent(id="a2", agent_id="data", text="extracted 42 records", timestamp=datetime.now(timezone.utc)),
    ActivityEvent(id="a3", agent_id="web_search", text="found 15 relevant sources", timestamp=datetime.now(timezone.utc)),
    ActivityEvent(id="a4", agent_id="research", text="started collecting market trends", timestamp=datetime.now(timezone.utc)),
    ActivityEvent(id="a5", agent_id="orchestrator", text="assigned task to Research Agent", timestamp=datetime.now(timezone.utc)),
]


@router.get("/stats", response_model=SimulationStats)
async def get_simulation_stats():
    """GET /api/v1/simulation/stats — powers the top stat-card row."""
    return _MOCK_STATS


@router.get("/activity", response_model=list[ActivityEvent])
async def get_activity_feed(limit: int = 20):
    """GET /api/v1/simulation/activity — powers the Activity Feed card."""
    return _MOCK_ACTIVITY[-limit:]


@router.post("/pause")
async def pause_simulation():
    """RESERVED: once app/agents/orchestrator.py exists, this should
    actually pause graph execution, not just flip a status string."""
    _MOCK_STATS.status = SimulationStatus.PAUSED
    await manager.broadcast("stats_updated", _MOCK_STATS.model_dump(mode="json"))
    return {"status": _MOCK_STATS.status}


@router.post("/resume")
async def resume_simulation():
    _MOCK_STATS.status = SimulationStatus.RUNNING
    await manager.broadcast("stats_updated", _MOCK_STATS.model_dump(mode="json"))
    return {"status": _MOCK_STATS.status}


@router.post("/stop")
async def stop_simulation():
    _MOCK_STATS.status = SimulationStatus.STOPPED
    await manager.broadcast("stats_updated", _MOCK_STATS.model_dump(mode="json"))
    return {"status": _MOCK_STATS.status}
