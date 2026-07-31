"""
app/models/schemas.py

Pydantic request/response models. These MUST stay in sync with
frontend/src/services/mockData.js and the TypeScript contracts in the
planning doc (Project3_TechStack_and_FileStructure.md, Section 2).

--------------------------------------------------------------------
IMPORTANT — camelCase vs snake_case (read this before adding a field):
--------------------------------------------------------------------
Every model below inherits from CamelModel, not BaseModel directly.
Python fields stay snake_case internally (idiomatic, e.g.
`total_agents`), but CamelModel automatically converts them to
camelCase when serialized to JSON (`totalAgents`) — because
JavaScript/React code expects camelCase, and a plain BaseModel would
have sent `total_agents` over the wire, which is exactly the bug that
caused the frontend to show "undefined" and "NaN" everywhere despite
the backend responding with 200 OK: single-word fields like `status`
looked fine (no case difference to get wrong), but every multi-word
field silently didn't match what the frontend was reading.

Rule going forward: define new fields in Python as snake_case, same as
always — CamelModel handles the JSON conversion for you. Don't name
fields camelCase in Python; that fights the language's own convention
and isn't necessary.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """
    Shared base for every schema in this file. Converts snake_case
    Python field names to camelCase in JSON output, and accepts EITHER
    casing on input (populate_by_name=True) so existing snake_case
    callers (curl, Python scripts, tests) still work alongside the
    frontend's camelCase requests.
    """
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    def model_dump(self, **kwargs):
        # FastAPI's response_model path already defaults to by_alias=True,
        # but code that calls .model_dump() directly — e.g. every
        # WebSocket broadcast in api/routes/*.py — does NOT go through
        # that path. Defaulting it here too means broadcasts are
        # camelCase automatically instead of relying on every call site
        # to remember `by_alias=True`.
        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs)

    def model_dump_json(self, **kwargs):
        kwargs.setdefault("by_alias", True)
        return super().model_dump_json(**kwargs)


# ==========================================================================
# Enums
# ==========================================================================

class AgentStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    WAITING = "waiting"
    ERROR = "error"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RelationshipType(str, Enum):
    DATA_FLOW = "data_flow"
    MESSAGE = "message"
    DEPENDENCY = "dependency"


class MessageKind(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"


class SimulationStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    OFFLINE = "offline"


# ==========================================================================
# Core models
# ==========================================================================

class Agent(CamelModel):
    id: str
    name: str                      # e.g. "Research Agent"
    role: str                      # e.g. "research", "orchestrator", "web_search"
    status: AgentStatus
    color: str                     # hex string, should match frontend's utils/colors.js role mapping
    icon: str | None = None

    # RESERVED — filled in once app/agents/ (LangGraph) is wired up:
    # current_token_usage: int | None = None
    # model_name: str | None = None


class AgentRelationship(CamelModel):
    source_agent_id: str
    target_agent_id: str
    type: RelationshipType
    active: bool = False


class TaskProgressStep(CamelModel):
    label: str
    done: bool


class Task(CamelModel):
    id: str                        # e.g. "T-1024"
    directive: str                 # instruction given to the agent
    assigned_agent_id: str
    status: TaskStatus
    priority: TaskPriority
    started_at: datetime
    duration_seconds: int
    progress_percent: int = Field(ge=0, le=100)
    progress_steps: list[TaskProgressStep] = []

    # The agent's actual output text once it finishes — this is what
    # was previously only visible in the terminal. Populated by
    # api/routes/tasks.py once an agent's run() completes; None while
    # queued/in progress.
    output: str | None = None
    # Populated instead of `output` if the agent's run() raised —
    # surfaces real failures to the dashboard instead of a silent hang.
    error: str | None = None


class Message(CamelModel):
    id: str
    from_agent_id: str
    to_agent_id: str
    kind: MessageKind
    content: str
    timestamp: datetime


class ActivityEvent(CamelModel):
    id: str
    agent_id: str
    text: str                      # e.g. "completed data analysis"
    timestamp: datetime


class SimulationStats(CamelModel):
    simulation_id: str | None = None
    status: SimulationStatus
    start_time: datetime | None = None
    duration_seconds: int = 0
    total_agents: int = 0
    active_agents: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    total_messages: int = 0
    avg_response_time_seconds: float = 0.0
    success_rate_percent: float = 0.0


# ==========================================================================
# Request bodies (for the "Quick Actions" panel: Add Agent / Create Task)
# ==========================================================================

class CreateAgentRequest(CamelModel):
    name: str
    role: str
    color: str | None = None       # if omitted, backend assigns one — see routes/agents.py


class CreateTaskRequest(CamelModel):
    directive: str
    assigned_agent_id: str
    priority: TaskPriority = TaskPriority.MEDIUM


# ==========================================================================
# Agent runtime stats — response time, token usage, call counts per agent
# ==========================================================================

class AgentRuntimeStats(CamelModel):
    """
    Real runtime stats for one agent, tracked by
    app/agents/stats_tracker.py. Every field starts at a genuine zero
    (and status starts "idle") and only changes when that agent's
    BaseAgent.run() actually executes — never a fabricated placeholder.
    This is what powers the frontend's Agents page (token usage, avg
    response time per agent) AND the live status shown in the Agent
    Relationship Graph (see api/routes/agents.py's GET /agents, which
    merges this real status into the roster).
    """
    agent_id: str
    status: AgentStatus = AgentStatus.IDLE
    calls_made: int = 0
    total_tokens_used: int = 0
    avg_response_time_seconds: float = 0.0
    last_response_time_seconds: float | None = None
    last_response_preview: str | None = None   # first ~200 chars of the agent's last output
    last_called_at: datetime | None = None
    model_used: str | None = None
