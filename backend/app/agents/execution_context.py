"""Validated per-run inputs and the request-local stage metrics sink.

This internal model describes supplied data. It does not choose or run a route.
"""
from contextvars import ContextVar
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError, field_validator, model_validator

from app.models.schemas import InputContractFailure, TaskExecutionMode

current_execution = ContextVar("current_execution", default=None)

AgentId = Literal["research", "data", "analysis", "summarizer", "report", "direct"]
OutputName = Literal["research_findings", "structured_data", "insights", "summary", "final_report", "final_answer"]
OUTPUT_BY_AGENT = {
    "research": "research_findings", "data": "structured_data", "analysis": "insights",
    "summarizer": "summary", "report": "final_report", "direct": "final_answer",
}


class AgentInputError(ValueError):
    """Safe structured error: never include rejected data or provider secrets."""

    def __init__(self, code: str, agent_id: str | None = None, missing_inputs=()):
        self.detail = InputContractFailure(code=code, agent_id=agent_id,
                                           missing_inputs=list(missing_inputs))
        message = {
            "invalid_context": "Execution context is malformed or exceeds the supported limits.",
            "directive_mismatch": "Execution context does not match the original directive.",
            "missing_required_input": "Summarization requires source material: supply reference context or an upstream result.",
        }.get(code, "Agent input contract validation failed.")
        super().__init__(message)


class InternalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AgentOutput(InternalModel):
    agent_id: AgentId
    name: OutputName
    text: StrictStr = Field(min_length=1, max_length=65536)

    @model_validator(mode="after")
    def validate_output(self):
        if OUTPUT_BY_AGENT[self.agent_id] != self.name or not self.text.strip():
            raise ValueError("Output must be nonblank and match its producing agent")
        return self


class RouteSelection(InternalModel):
    """Optional future plan metadata, separate from executed StageExecution rows."""
    selected_agents: tuple[AgentId, ...] = Field(min_length=1)
    skipped_agents: tuple[AgentId, ...] = ()

    @model_validator(mode="after")
    def validate_selection(self):
        all_agents = self.selected_agents + self.skipped_agents
        if len(all_agents) != len(set(all_agents)):
            raise ValueError("Selected and skipped agents must be unique and disjoint")
        return self


class ExecutionContext(InternalModel):
    original_directive: StrictStr = Field(min_length=1, max_length=10000)
    execution_mode: TaskExecutionMode = TaskExecutionMode.SINGLE_AGENT
    task_type: StrictStr | None = Field(default=None, max_length=80)
    # Existing upload parser bounds each file at 6,000 characters plus its
    # truncation notice. This ceiling includes three notices and file labels.
    uploaded_context: StrictStr | None = Field(default=None, max_length=19000)
    benchmark_context: StrictStr | None = Field(default=None, max_length=3500)
    source_text: StrictStr | None = Field(default=None, max_length=18000)
    prior_outputs: tuple[AgentOutput, ...] = ()
    route: RouteSelection | None = None

    @field_validator("original_directive", "uploaded_context", "benchmark_context", "source_text")
    @classmethod
    def nonblank(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Supplied text must not be blank")
        return value

    @model_validator(mode="after")
    def unique_outputs(self):
        names = [output.name for output in self.prior_outputs]
        if len(names) != len(set(names)):
            raise ValueError("Prior output names must be unique")
        if self.route and any(output.agent_id not in self.route.selected_agents for output in self.prior_outputs):
            raise ValueError("Only selected agents may supply prior outputs")
        return self

    @property
    def available_outputs(self) -> tuple[str, ...]:
        return tuple(output.name for output in self.prior_outputs)

    @property
    def available_inputs(self) -> tuple[str, ...]:
        return ("original_directive",) + tuple(
            name for name in ("source_text", "uploaded_context", "benchmark_context")
            if getattr(self, name) is not None
        ) + self.available_outputs

    def missing_inputs(self, names) -> tuple[str, ...]:
        return tuple(name for name in names if name not in self.available_inputs)

    def output(self, name: str) -> AgentOutput | None:
        return next((output for output in self.prior_outputs if output.name == name), None)

    def with_output(self, agent_id: AgentId, text: str):
        """Add only a successful real result; never synthesize skipped artifacts."""
        try:
            output = AgentOutput(agent_id=agent_id, name=OUTPUT_BY_AGENT[agent_id], text=text)
            values = self.model_dump()
            values["prior_outputs"] = (*self.prior_outputs, output)
            return ExecutionContext.model_validate(values)
        except (KeyError, ValidationError) as exc:
            raise AgentInputError("invalid_context", agent_id) from exc


def coerce_context(directive: str, context, agent_id: str | None = None) -> ExecutionContext:
    """Accept existing flat internal callers at one strict compatibility boundary."""
    if isinstance(context, ExecutionContext):
        if directive != context.original_directive:
            raise AgentInputError("directive_mismatch", agent_id)
        return context
    try:
        if context is None:
            context = {}
        if not isinstance(context, dict):
            raise ValueError("Expected execution context")
        source_names = {"uploaded_context", "benchmark_context", "source_text"}
        if set(context) - source_names - set(OUTPUT_BY_AGENT.values()):
            raise ValueError("Unknown context field")
        outputs = tuple(AgentOutput(agent_id=aid, name=name, text=context[name])
                        for aid, name in OUTPUT_BY_AGENT.items() if name in context)
        return ExecutionContext(original_directive=directive, prior_outputs=outputs,
                                **{name: context[name] for name in source_names if name in context})
    except (ValueError, TypeError) as exc:
        raise AgentInputError("invalid_context", agent_id) from exc
