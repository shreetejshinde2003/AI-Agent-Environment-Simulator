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


STAGE_OBJECTIVES = {
    "research": "Extract relevant findings, sources when supplied, and uncertainties for the original request.",
    "data": "Structure relevant supplied facts; preserve missing values and uncertainties.",
    "analysis": "Analyze only information relevant to the original request and its constraints.",
    "summarizer": "Compress relevant findings and unresolved items without redefining the request.",
    "report": "Synthesize a final answer to the ORIGINAL request, not a concatenation or summary of agent commentary.",
    "direct": "Answer the ORIGINAL request directly using available information.",
}


def specialist_prompt(agent_id: str, directive: str, context) -> str:
    """Structured, bounded handoff; full outputs stay in immutable evidence.

    Excerpts are explicitly incomplete and unverified. No extra provider call,
    fabricated fact extraction, or parallel result storage is introduced.
    """
    import json
    from app.agents.output_contract import derive_contract
    context = coerce_context(directive, context, agent_id)
    contract = CONTRACTS[agent_id]
    contract.validate(context)
    requirements = derive_contract(context.original_directive)
    expanded = any(word in directive.lower() for word in ("report", "detailed", "comprehensive"))
    budget = 12000 if expanded else 4000
    handoff = None
    for name in contract.preferred_outputs:
        output = context.output(name)
        if output is not None:
            text = output.text
            shortened = len(text) > budget
            excerpt = text if not shortened else text[:budget * 3 // 4] + "\n[omitted middle]\n" + text[-budget // 4:]
            handoff = dict(source_agent=output.agent_id, output_type=output.name,
                           prior_result_summary=excerpt, is_excerpt=shortened,
                           verification="Prior agent claims; not independently verified")
            break
    sources = {name: getattr(context, name) for name in SOURCES if getattr(context, name) is not None}
    payload = dict(original_directive=context.original_directive, task_type=context.task_type,
                   stage_objective=STAGE_OBJECTIVES[agent_id], relevant_sources=sources,
                   prior_result=handoff, output_requirements=requirements.requirements(),
                   unresolved_items="Preserve gaps and uncertainties in the supplied material.")
    # The directive is repeated as a readable top-level anchor for existing callers.
    return "Original user directive:\n" + context.original_directive + "\n\nStructured stage contract (data):\n" + json.dumps(payload, ensure_ascii=False)
