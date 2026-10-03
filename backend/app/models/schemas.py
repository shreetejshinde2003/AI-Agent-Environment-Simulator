"""
app/models/schemas.py

Pydantic request/response models shared by REST, persistence and WebSocket.
The frontend reads the same camelCase contracts from authoritative REST state.

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
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, computed_field
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


class TaskExecutionMode(str, Enum):
    SINGLE = "single"
    FIXED = "fixed"
    ADAPTIVE = "adaptive"
    # Older /tasks callers selected one specialist. Keep this distinct from
    # the neutral single-agent experimental baseline.
    SINGLE_AGENT = "single_agent"
    FULL_PIPELINE = "fixed"  # Python enum-name compatibility; JSON remains canonical.


def normalize_execution_mode(value):
    # Existing V1/V2 snapshots and clients used this name for the fixed path.
    return TaskExecutionMode.FIXED if value == "full_pipeline" else value


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
    implemented: bool = False


class AgentRelationship(CamelModel):
    source_agent_id: str
    target_agent_id: str
    type: RelationshipType
    active: bool = False


class TaskProgressStep(CamelModel):
    label: str
    done: bool


class InputContractFailure(CamelModel):
    code: str
    agent_id: str | None = None
    missing_inputs: list[str] = Field(default_factory=list)


class StageExecution(CamelModel):
    agent_id: str
    output_key: str
    status: str = "waiting"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    output: str | None = None
    error: str | None = None
    input_error: InputContractFailure | None = None


class RunEvent(CamelModel):
    id: str
    type: str
    timestamp: datetime
    agent_id: str | None = None
    text: str


class UploadedContext(CamelModel):
    id: str
    filename: str
    format: str
    size_bytes: int
    created_at: datetime
    preview: str
    prepared_context: str
    truncated: bool = False
    row_count: int | None = None
    columns: list[str] = Field(default_factory=list)


class DatasetQuality(CamelModel):
    manager_id_nan_as_null: int = 0
    outer_whitespace_by_field: dict[str, int] = Field(default_factory=dict)
    protected_fields: list[str] = Field(default_factory=list)
    confidential_fields: list[str] = Field(default_factory=list)


class DatasetMetadata(CamelModel):
    dataset_id: str
    name: str
    family: str
    size_variant: str
    source_filename: str
    record_count: int
    schema_columns: list[dict[str, str]]
    checksum: str
    active: bool
    imported_at: datetime
    quality: DatasetQuality

class RunProvenance(CamelModel):
    """Immutable evidence describing the conditions under which a run began."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_protocol_version: str
    input_fingerprint: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )
    directive_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    # Preserve what the caller supplied before Adaptive routing can classify
    # and replace Task.task_type with the inferred route task type.
    requested_task_type: str | None = None

    dataset_id: str | None = None
    dataset_checksum: str | None = None
    benchmark_context_sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )
    upload_context_sha256: tuple[str, ...] = ()

    provider: str
    configured_model: str
    max_output_tokens: int = Field(gt=0)

    prompt_protocol_version: str
    contracts_version: str
    router_version: str | None = None

class ObjectiveEvaluation(CamelModel):
    """Measured execution evidence; never an LLM judgment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["completed", "failed"]
    elapsed_seconds: float | None = Field(default=None, ge=0)
    agent_invocation_count: int = Field(ge=0)
    handoff_count: int = Field(ge=0)
    token_coverage: Literal["unavailable", "partial", "complete"]
    total_tokens: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_token_semantics(self):
        if self.token_coverage == "complete" and self.total_tokens is None:
            raise ValueError(
                "Complete token coverage requires total_tokens."
            )

        if self.token_coverage != "complete" and self.total_tokens is not None:
            raise ValueError(
                "total_tokens must be null unless token coverage is complete."
            )

        return self


class QualityCriterion(CamelModel):
    """One blinded evaluator judgment under the versioned quality rubric."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Literal[
        "task_fulfillment",
        "completeness",
        "coherence",
        "grounding",
    ]
    applicable: bool = True
    score: int | None = Field(default=None, ge=1, le=5)
    rationale: str = Field(min_length=1, max_length=600)

    @model_validator(mode="after")
    def validate_applicability(self):
        if self.applicable and self.score is None:
            raise ValueError(
                "Applicable criteria require a score."
            )

        if not self.applicable and self.score is not None:
            raise ValueError(
                "Non-applicable criteria must not have a score."
            )

        return self


class QualityJudgment(CamelModel):
    """Blinded output-quality judgment; not factual ground truth."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_protocol_version: Literal["evaluation-v1"] = "evaluation-v1"
    rubric_version: Literal["quality-rubric-v1"] = "quality-rubric-v1"

    evaluator_provider: str
    evaluator_model: str

    # The evaluator prompt must not reveal Single / Fixed / Adaptive.
    treatment_blinded: Literal[True] = True

    output_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    criteria: tuple[
        QualityCriterion,
        QualityCriterion,
        QualityCriterion,
        QualityCriterion,
    ]

    @model_validator(mode="after")
    def validate_rubric_dimensions(self):
        expected = (
            "task_fulfillment",
            "completeness",
            "coherence",
            "grounding",
        )

        actual = tuple(item.name for item in self.criteria)

        if actual != expected:
            raise ValueError(
                "Quality criteria must appear exactly once in rubric order."
            )

        return self


class RunEvaluation(CamelModel):
    """Evaluation evidence attached to one completed research run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    experiment_id: str | None = None

    input_fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    evaluated_at: datetime
    objective: ObjectiveEvaluation
    quality: QualityJudgment | None = None
class RoutePlan(CamelModel):
    """Versioned deterministic routing metadata, never model reasoning."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    router_version: Literal["rules-v1"] = "rules-v1"
    execution_mode: Literal["adaptive"] = "adaptive"
    task_type: str
    selected_agent_ids: tuple[str, ...]
    skipped_agent_ids: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    available_inputs: tuple[str, ...]
    reasons: tuple[str, ...]
    validation_status: Literal["valid", "invalid"]
    validation_error: str | None = None


def display_title(directive: str, title: str | None = None) -> str:
    """Stable literal excerpt, not a claim of semantic summarization."""
    text = " ".join((title or "").split()) or " ".join(directive.split()) or "Untitled simulation"
    return text if len(text) <= 80 else text[:77].rstrip() + "…"


class Task(CamelModel):
    id: str                        # e.g. "T-1024"
    directive: str                 # instruction given to the agent
    assigned_agent_id: str
    status: TaskStatus
    priority: TaskPriority
    execution_mode: TaskExecutionMode = TaskExecutionMode.SINGLE_AGENT
    started_at: datetime
    duration_seconds: int
    progress_percent: int = Field(ge=0, le=100)
    progress_steps: list[TaskProgressStep] = Field(default_factory=list)

    # The agent's actual output text once it finishes — this is what
    # was previously only visible in the terminal. Populated by
    # api/routes/tasks.py once an agent's run() completes; None while
    # queued/in progress.
    output: str | None = None
    # Populated instead of `output` if the agent's run() raised —
    # surfaces real failures to the dashboard instead of a silent hang.
    error: str | None = None
    simulation_id: str | None = None
    owner_id: str | None = None  # Shared workspace; no authentication claim.
    created_at: datetime | None = None
    execution_started_at: datetime | None = None
    completed_at: datetime | None = None
    elapsed_seconds: float | None = None
    stages: list[StageExecution] = Field(default_factory=list)
    events: list[RunEvent] = Field(default_factory=list)
    messages: list["Message"] = Field(default_factory=list)
    activities: list["ActivityEvent"] = Field(default_factory=list)
    uploads: list[UploadedContext] = Field(default_factory=list)
    dataset_id: str | None = None
    dataset_checksum: str | None = None
    task_type: str | None = None
    benchmark_context: str | None = None
    evaluation_scores: dict[str, float] | None = None
    evaluation: RunEvaluation | None = None
    input_error: InputContractFailure | None = None
    title: str | None = None
    route_plan: RoutePlan | None = None
    provenance: RunProvenance | None = None
    experiment_id: str | None = None

    @model_validator(mode="after")
    def readable_title(self):
        self.title = display_title(self.directive, self.title)
        return self

    @computed_field
    @property
    def agent_invocation_count(self) -> int:
        # Started stage attempts, not proof a provider request reached Groq.
        return sum(stage.started_at is not None for stage in self.stages)

    @computed_field
    @property
    def handoff_count(self) -> int:
        return len(self.messages)

    @field_validator("execution_mode", mode="before")
    @classmethod
    def legacy_execution_mode(cls, value):
        return normalize_execution_mode(value)


class Message(CamelModel):
    id: str
    from_agent_id: str
    to_agent_id: str
    kind: MessageKind
    content: str
    timestamp: datetime
    simulation_id: str | None = None
    output_key: str | None = None


class ActivityEvent(CamelModel):
    id: str
    agent_id: str
    text: str                      # e.g. "completed data analysis"
    timestamp: datetime
    simulation_id: str | None = None


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
    directive: str = Field(min_length=1, max_length=10000)
    title: str | None = Field(default=None, max_length=120)
    assigned_agent_id: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    execution_mode: TaskExecutionMode = TaskExecutionMode.SINGLE_AGENT
    upload_ids: list[str] = Field(default_factory=list, max_length=3)
    dataset_id: str | None = None
    task_type: str | None = Field(default=None, max_length=80)

    @field_validator("execution_mode", mode="before")
    @classmethod
    def legacy_execution_mode(cls, value):
        return normalize_execution_mode(value)


class CreateOrganizationRequest(CamelModel):
    """Create one explicitly shared Organization workspace."""

    name: str = Field(
        min_length=2,
        max_length=120,
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str):
        normalized = " ".join(
            value.strip().split()
        )

        if len(normalized) < 2:
            raise ValueError(
                "Organization name must contain at least 2 characters."
            )

        return normalized


class OrganizationCreated(CamelModel):
    """Organization creation response.

    join_code is intentionally returned only at creation time. Persistent
    storage contains only its digest.
    """

    id: str
    kind: Literal["organization"] = "organization"
    name: str
    membership_role: Literal["owner"] = "owner"
    join_code: str


class CreateSimulationRequest(CreateTaskRequest):
    assigned_agent_id: str = "orchestrator"
    execution_mode: TaskExecutionMode = TaskExecutionMode.FIXED


class CreateMatchedExperimentRequest(CamelModel):
    """One immutable research input executed through all three research modes."""

    directive: str = Field(min_length=1, max_length=10000)
    title: str | None = Field(default=None, max_length=120)
    priority: TaskPriority = TaskPriority.MEDIUM
    upload_ids: list[str] = Field(default_factory=list, max_length=3)
    dataset_id: str | None = None
    task_type: str | None = Field(default=None, max_length=80)

class MatchedExperimentRun(CamelModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_mode: Literal["single", "fixed", "adaptive"]
    task_id: str


class MatchedExperiment(CamelModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_id: str
    created_at: datetime
    input_fingerprint: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )
    runs: tuple[MatchedExperimentRun, MatchedExperimentRun, MatchedExperimentRun]

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
