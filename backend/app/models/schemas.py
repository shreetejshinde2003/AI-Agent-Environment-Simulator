"""
app/models/schemas.py

Pydantic request/response models. These MUST stay in sync with
frontend/src/services/mockData.js and the TypeScript contracts in the
planning doc (Project3_TechStack_and_FileStructure.md, Section 2).

Rule of thumb: if you change a field here, go update the frontend mock
data and TypeScript types in the same commit — the whole point of
freezing this contract early is that frontend and backend never drift.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


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



# ==========================================================================
# Core models
# ==========================================================================

class Agent(BaseModel):
    id: str
    name: str                      # e.g. "Research Agent"
    role: str                      # e.g. "research", "orchestrator", "web_search"
    status: AgentStatus
    color: str                     # hex string, should match frontend's utils/colors.js role mapping
    icon: str | None = None

    # RESERVED — filled in once app/agents/ (LangGraph) is wired up:
    # current_token_usage: int | None = None
    # model_name: str | None = None


class AgentRelationship(BaseModel):
    source_agent_id: str
    target_agent_id: str
    type: RelationshipType
    active: bool = False


class TaskProgressStep(BaseModel):
    label: str
    done: bool


class Task(BaseModel):
    id: str                        # e.g. "T-1024"
    directive: str                 # instruction given to the agent
    assigned_agent_id: str
    status: TaskStatus
    priority: TaskPriority
    started_at: datetime
    duration_seconds: int
    progress_percent: int = Field(ge=0, le=100)
    progress_steps: list[TaskProgressStep] = []


class Message(BaseModel):
    id: str
    from_agent_id: str
    to_agent_id: str
    kind: MessageKind
    content: str
    timestamp: datetime


class ActivityEvent(BaseModel):
    id: str
    agent_id: str
    text: str                      # e.g. "completed data analysis"
    timestamp: datetime


class SimulationStats(BaseModel):
    simulation_id: str
    status: SimulationStatus
    start_time: datetime
    duration_seconds: int
    total_agents: int
    active_agents: int
    total_tasks: int
    completed_tasks: int
    total_messages: int
    avg_response_time_seconds: float
    success_rate_percent: float


class AgentRuntimeStats(BaseModel):
    agent_id: str

    calls_made: int = 0
    total_tokens_used: int = 0

    avg_response_time_seconds: float = 0.0
    last_response_time_seconds: float = 0.0

    last_response_preview: str = ""

    last_called_at: datetime | None = None

    model_used: str | None = None
    
# ==========================================================================
# Request bodies (for the "Quick Actions" panel: Add Agent / Create Task)
# ==========================================================================

class CreateAgentRequest(BaseModel):
    name: str
    role: str
    color: str | None = None       # if omitted, backend assigns one — see routes/agents.py


class CreateTaskRequest(BaseModel):
    directive: str
    assigned_agent_id: str
    priority: TaskPriority = TaskPriority.MEDIUM
