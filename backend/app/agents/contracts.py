"""Inspectable specialist capabilities and input binding; no routing decisions."""
from dataclasses import dataclass
from types import MappingProxyType

from app.agents.execution_context import AgentInputError, ExecutionContext, coerce_context


@dataclass(frozen=True)
class AgentContract:
    agent_id: str
    capabilities: tuple[str, ...]
    output: str
    required_inputs: tuple[str, ...] = ("original_directive",)
    optional_inputs: tuple[str, ...] = ()
    required_any_of: tuple[str, ...] = ()
    preferred_outputs: tuple[str, ...] = ()

    def validate(self, context: ExecutionContext):
        missing = context.missing_inputs(self.required_inputs)
        if missing:
            raise AgentInputError("invalid_context", self.agent_id, missing)
        if self.required_any_of and not set(self.required_any_of).intersection(context.available_inputs):
            # The old individual-specialist action treats its directive as
            # standalone source material. A future adaptive plan must name an
            # actual source rather than assuming the user supplied one.
            if context.execution_mode.value == "single_agent":
                return
            raise AgentInputError("missing_required_input", self.agent_id, self.required_any_of)


SOURCES = ("source_text", "uploaded_context", "benchmark_context")
CONTRACTS = MappingProxyType({
    "research": AgentContract("research", ("knowledge_research",), "research_findings",
                              optional_inputs=SOURCES),
    "data": AgentContract("data", ("structure", "extract"), "structured_data",
                          optional_inputs=SOURCES + ("research_findings",),
                          preferred_outputs=("research_findings",)),
    "analysis": AgentContract("analysis", ("analyze", "compare", "reason"), "insights",
                              optional_inputs=SOURCES + ("structured_data", "research_findings"),
                              preferred_outputs=("structured_data", "research_findings")),
    "summarizer": AgentContract("summarizer", ("summarize",), "summary",
                                optional_inputs=SOURCES + ("insights", "structured_data", "research_findings"),
                                required_any_of=SOURCES + ("insights", "structured_data", "research_findings"),
                                preferred_outputs=("insights", "structured_data", "research_findings")),
    "report": AgentContract("report", ("report", "synthesize"), "final_report",
                            optional_inputs=SOURCES + ("summary", "insights", "structured_data", "research_findings"),
                            preferred_outputs=("summary", "insights", "structured_data", "research_findings")),
    "direct": AgentContract("direct", ("direct_answer",), "final_answer",
                            optional_inputs=("uploaded_context", "benchmark_context")),
})


def specialist_prompt(agent_id: str, directive: str, context) -> str:
    """Use the preferred available artifact, keeping fixed handoffs primary.

    Omitted optional sources have no empty/fabricated prompt sections. The full
    typed context retains all outputs for later stages and future validation.
    """
    context = coerce_context(directive, context, agent_id)
    contract = CONTRACTS[agent_id]
    contract.validate(context)
    parts = [f"Original user directive:\n{context.original_directive}"]
    if context.task_type:
        parts.append(f"Task type:\n{context.task_type}")
    preferred_output = None
    for name in contract.preferred_outputs:
        output = context.output(name)
        if output is not None:
            parts.append(f"Supplied {output.name} (from {output.agent_id}):\n{output.text}")
            preferred_output = output
            break
    for name, label in (
        ("source_text", "Supplied source material"),
        ("uploaded_context", "Uploaded reference context"),
        ("benchmark_context", "Validated benchmark aggregates (not individual records)"),
    ):
        if preferred_output is not None and name in ("source_text", "uploaded_context") \
                and agent_id not in ("research", "data"):
            # Fixed Analysis/Summarizer/Report continue consuming their usual
            # predecessor rather than adding earlier raw inputs to the prompt.
            continue
        value = getattr(context, name)
        if value is not None:
            parts.append(f"{label}:\n{value}")
    return "\n\n".join(parts)
