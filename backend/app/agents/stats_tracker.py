"""
app/agents/stats_tracker.py

In-memory registry of each agent's REAL runtime stats — calls made,
tokens used, response times. Every agent starts at a genuine zero and
only updates when app/agents/base_agent.py's `run()` actually executes
a real LLM call.

This mirrors the same rule the frontend follows (see
frontend/src/hooks/useSimulationData.js): no fabricated numbers, ever.
Until the agents in this folder are wired up to a real LLM and
actually invoked by the orchestrator, this stays at zero — which is
the honest, correct state for a system with no agents running yet.

RESERVED for persistence: this is in-memory only, matching the rest of
the backend's current scope (see app/storage/database.py's checklist).
Stats reset on server restart. Move this into storage/ once real
persistence is needed — the shape (AgentRuntimeStats) won't need to change.
"""

from datetime import datetime, timezone

from app.models.schemas import AgentRuntimeStats

# The six agents + the orchestrator. Must match the ids used in
# app/api/routes/agents.py's _MOCK_AGENTS and the frontend's
# utils/colors.js AGENT_ROLE_COLORS — these ids are the contract
# between backend, frontend, and the agent files in this folder.
KNOWN_AGENT_IDS = [
    "orchestrator",
    "research",
    "data",
    "web_search",
    "analysis",
    "summarizer",
    "report",
]


class AgentStatsTracker:
    def __init__(self) -> None:
        self._stats: dict[str, AgentRuntimeStats] = {}
        for agent_id in KNOWN_AGENT_IDS:
            self.register(agent_id)

    def register(self, agent_id: str) -> None:
        """Safe to call multiple times — only creates the entry once."""
        if agent_id not in self._stats:
            self._stats[agent_id] = AgentRuntimeStats(agent_id=agent_id)

    def set_status(self, agent_id: str, status) -> None:
        """Called by BaseAgent.run() when an agent starts/finishes a
        real call — this is what makes the Agent Relationship Graph's
        "active"/"idle" status genuine instead of a fixed roster value."""
        self.register(agent_id)
        self._stats[agent_id].status = status

    def record_call(
        self,
        agent_id: str,
        response_time_seconds: float,
        tokens_used: int,
        response_preview: str,
        model_used: str | None = None,
    ) -> None:
        """Called by BaseAgent.run() after every real agent invocation."""
        self.register(agent_id)
        stats = self._stats[agent_id]

        # Running average, not just "most recent value" — matters once
        # an agent has made many calls over a long simulation.
        new_count = stats.calls_made + 1
        stats.avg_response_time_seconds = (
            (stats.avg_response_time_seconds * stats.calls_made) + response_time_seconds
        ) / new_count

        stats.calls_made = new_count
        stats.total_tokens_used += tokens_used
        stats.last_response_time_seconds = response_time_seconds
        stats.last_response_preview = response_preview[:200]
        stats.last_called_at = datetime.now(timezone.utc)
        if model_used:
            stats.model_used = model_used

    def get(self, agent_id: str) -> AgentRuntimeStats | None:
        return self._stats.get(agent_id)

    def get_all(self) -> list[AgentRuntimeStats]:
        return list(self._stats.values())

    def reset(self, agent_id: str | None = None) -> None:
        """RESERVED: useful for a 'Clear All' quick action later — not
        wired to any route yet."""
        if agent_id:
            self._stats[agent_id] = AgentRuntimeStats(agent_id=agent_id)
        else:
            self._stats = {aid: AgentRuntimeStats(agent_id=aid) for aid in KNOWN_AGENT_IDS}


# Single shared instance — import this everywhere, don't instantiate a new one.
stats_tracker = AgentStatsTracker()
