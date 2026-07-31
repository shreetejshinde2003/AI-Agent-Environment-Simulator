"""
app/api/routes/simulation.py

Top-level simulation control + stats — powers the stat-card row
(Agents Active, Tasks Completed, Messages, Avg Response Time, Success
Rate), the Activity Feed, and the Topbar's Replay/Pause/Stop controls.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from app.agents.stats_tracker import stats_tracker
from app.models.schemas import ActivityEvent, AgentStatus, SimulationStats, SimulationStatus
from app.websocket.manager import manager

router = APIRouter(prefix="/simulation", tags=["simulation"])


# ----------------------------------------------------------------------
# Real session state — NOT fabricated placeholder numbers. simulation_id
# and start_time are genuine facts about this server process (when it
# actually started); task/message counters start at true zero and only
# increment via register_task_created()/register_task_finished() below,
# called from api/routes/tasks.py as real tasks actually run.
# total_agents/active_agents are NOT stored here at all — see
# get_simulation_stats(), which computes them live from
# app/agents/stats_tracker.py so "active" always reflects agents that
# are genuinely mid-call right now, not a fixed guess.
# ----------------------------------------------------------------------
_SERVER_STARTED_AT = datetime.now(timezone.utc)

_MOCK_STATS = SimulationStats(
    simulation_id=f"SIM-{_SERVER_STARTED_AT.strftime('%Y%m%d-%H%M%S')}",
    status=SimulationStatus.RUNNING,
    start_time=_SERVER_STARTED_AT,
    duration_seconds=0,
    total_agents=0,   # overwritten live in get_simulation_stats()
    active_agents=0,  # overwritten live in get_simulation_stats()
    total_tasks=0,
    completed_tasks=0,
    total_messages=0,
    avg_response_time_seconds=0.0,
    success_rate_percent=0.0,
)

_MOCK_ACTIVITY: list[ActivityEvent] = []


@router.get("/stats", response_model=SimulationStats)
async def get_simulation_stats():
    """
    GET /api/v1/simulation/stats — powers the top stat-card row.

    total_agents / active_agents are computed HERE, live, from
    stats_tracker — not stored as static numbers — so "N active" always
    reflects agents genuinely mid-call right now. duration_seconds is
    computed from the real server start time.
    """
    all_stats = stats_tracker.get_all()
    _MOCK_STATS.total_agents = len(all_stats)
    _MOCK_STATS.active_agents = sum(1 for s in all_stats if s.status == AgentStatus.ACTIVE)
    _MOCK_STATS.duration_seconds = int((datetime.now(timezone.utc) - _SERVER_STARTED_AT).total_seconds())

    # Local import avoids a circular import at module load time (this
    # module is imported by tasks.py; messages.py isn't, so this is safe).
    from app.api.routes.messages import get_message_count
    _MOCK_STATS.total_messages = get_message_count()

    return _MOCK_STATS


@router.get("/activity", response_model=list[ActivityEvent])
async def get_activity_feed(limit: int = 20):
    """GET /api/v1/simulation/activity — powers the Activity Feed card."""
    return _MOCK_ACTIVITY[-limit:]


# ----------------------------------------------------------------------
# Helpers used by OTHER routes (currently api/routes/tasks.py) so a real
# task actually moves the dashboard's aggregate numbers, instead of
# _MOCK_STATS just sitting at fixed placeholder values forever. Kept
# here (not duplicated) since this module already owns _MOCK_STATS /
# _MOCK_ACTIVITY — everything that touches them goes through one place.
# ----------------------------------------------------------------------

async def record_activity(agent_id: str, text: str) -> None:
    """Appends a real activity line and broadcasts it — used whenever
    an agent actually starts/finishes/fails a task."""
    event = ActivityEvent(
        id=f"a-{uuid.uuid4().hex[:8]}",
        agent_id=agent_id,
        text=text,
        timestamp=datetime.now(timezone.utc),
    )
    _MOCK_ACTIVITY.append(event)
    await manager.broadcast("activity_event", event.model_dump(mode="json"))


async def register_task_created() -> None:
    """Call when a new task is created — keeps totalTasks real."""
    _MOCK_STATS.total_tasks += 1
    await manager.broadcast("stats_updated", _MOCK_STATS.model_dump(mode="json"))


async def register_task_finished(response_time_seconds: float, success: bool) -> None:
    """
    Call when a real agent run finishes (success or failure) — updates
    completedTasks, totalMessages, avgResponseTimeSeconds, and
    successRatePercent from REAL numbers, not the static placeholders
    _MOCK_STATS started with.
    """
    if success:
        _MOCK_STATS.completed_tasks += 1

    # Running average over completed+failed attempts so far.
    attempts_so_far = _MOCK_STATS.completed_tasks + (
        0 if success else 1
    )
    if attempts_so_far > 0:
        _MOCK_STATS.avg_response_time_seconds = (
            (_MOCK_STATS.avg_response_time_seconds * (attempts_so_far - 1)) + response_time_seconds
        ) / attempts_so_far

    if _MOCK_STATS.total_tasks > 0:
        _MOCK_STATS.success_rate_percent = round(
            (_MOCK_STATS.completed_tasks / _MOCK_STATS.total_tasks) * 100, 1
        )

    await manager.broadcast("stats_updated", _MOCK_STATS.model_dump(mode="json"))


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
