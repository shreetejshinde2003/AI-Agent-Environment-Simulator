"""Deterministic capability routing. No model calls and no fabricated artifacts."""
import re

from app.agents.contracts import CONTRACTS
from app.agents.execution_context import ExecutionContext
from app.models.schemas import RoutePlan

SPECIALISTS = ("research", "data", "analysis", "summarizer", "report")
TASK_TYPES = ("summarization", "transformation", "analysis", "reporting",
              "research_synthesis", "structured_data_analysis", "mixed")
CAPABILITIES = {
    "summarization": {"summarize"}, "transformation": {"structure"},
    "analysis": {"analyze"}, "reporting": set(),
    "research_synthesis": {"knowledge_research"},
    "structured_data_analysis": {"structure", "analyze"},
}
PATTERNS = {
    "summarization": r"\b(summarize|summarise|summary|condense|summarization)\b",
    "transformation": r"\b(extract|transform|convert|reformat|structure)\b",
    "analysis": r"\b(analyze|analyse|analysis|compare|comparison|reason|tradeoffs?|implications?)\b",
    "research_synthesis": r"\b(research|investigate|explain|define|overview)\b",
}


def inline_source(directive: str) -> str | None:
    """Only an explicit source delimiter counts as source material, not a guessed fact."""
    match = re.search(r"(?:^|\n)(?:source|text):\s*(\S[\s\S]*)", directive, re.I)
    return match.group(1).strip() if match else None


def validate_route(plan: RoutePlan, context: ExecutionContext) -> RoutePlan:
    """Symbolic dependency validation: names only; never synthesize fake output text."""
    available = set(context.available_inputs)
    selected = plan.selected_agent_ids
    error = None
    if not selected or len(selected) != len(set(selected)) or any(a not in SPECIALISTS for a in selected):
        error = "Route must select unique implemented specialists."
    elif selected[-1] != "report":
        error = "Route must finish with Report for the final result."
    elif selected != tuple(a for a in SPECIALISTS if a in selected):
        error = "Route violates the supported specialist dependency order."
    elif plan.skipped_agent_ids != tuple(a for a in SPECIALISTS if a not in selected):
        error = "Selected and skipped specialists must form an exact partition."
    elif plan.available_inputs != tuple(sorted(available)):
        error = "Route input metadata does not match prepared context."
    else:
        capabilities = set()
        for aid in selected:
            contract = CONTRACTS[aid]
            if set(contract.required_inputs) - available or (
                contract.required_any_of and not set(contract.required_any_of) & available
            ):
                error = f"{aid} requires source material not available on this route."
                break
            capabilities.update(contract.capabilities)
            available.add(contract.output)
        if error is None and set(plan.required_capabilities) - capabilities:
            error = "Route does not provide every required capability."
    return plan.model_copy(update={"validation_status": "invalid" if error else "valid",
                                   "validation_error": error})


def plan_route(context: ExecutionContext, upload_formats=()) -> RoutePlan:
    """Explicit type overrides inferred intent; mixed combines detected capabilities."""
    # Inspect the instruction only, never treat untrusted uploaded/source prose as rules.
    instruction = re.split(r"(?:^|\n)(?:source|text):", context.original_directive, flags=re.I)[0]
    normalized = " ".join(instruction.casefold().split())
    detected = {name for name, pattern in PATTERNS.items() if re.search(pattern, normalized)}
    structured = bool(context.benchmark_context) or bool(set(upload_formats) & {"csv", "json"})
    explicit = re.sub(r"[\s-]+", "_", context.task_type.strip().casefold()) if context.task_type else None
    if explicit and explicit not in TASK_TYPES:
        raise ValueError("Unsupported adaptive taskType; choose a documented category or omit it.")
    task_type = explicit or ("mixed" if len(detected) > 1 else next(iter(detected), None))
    if task_type is None:
        task_type = "structured_data_analysis" if structured else (
            "reporting" if re.search(r"\b(report|draft|write)\b", normalized) else "research_synthesis")
    if not explicit and task_type == "analysis" and structured:
        task_type = "structured_data_analysis"
    required = set(CAPABILITIES.get(task_type, set()))
    if task_type == "mixed":
        for name in sorted(detected):
            required.update(CAPABILITIES[name])
        if not required:
            required.update({"analyze", "summarize"})
        if structured and "analyze" in required:
            required.add("structure")
    required.add("report")
    selected = tuple(a for a in SPECIALISTS if set(CONTRACTS[a].capabilities) & required)
    reasons = [f"{'Explicit' if explicit else 'Rule-inferred'} task type: {task_type}."]
    if structured:
        reasons.append("Structured CSV/JSON upload or benchmark aggregates are available.")
    reasons.append("Required capabilities: " + ", ".join(sorted(required)) + ".")
    reasons.append("Select matching capability providers in dependency order; Report presents the result. Other specialists are skipped.")
    plan = RoutePlan(task_type=task_type, selected_agent_ids=selected,
                     skipped_agent_ids=tuple(a for a in SPECIALISTS if a not in selected),
                     required_capabilities=tuple(sorted(required)),
                     available_inputs=tuple(sorted(context.available_inputs)),
                     reasons=tuple(reasons), validation_status="invalid")
    return validate_route(plan, context)
