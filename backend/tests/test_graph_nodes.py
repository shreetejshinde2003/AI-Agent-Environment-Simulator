import pytest

from app.agents.execution_context import ExecutionContext, RouteSelection
from app.agents.graph_nodes import GRAPH_NODES, make_agent_node
from app.agents.graph_state import GraphRunState
from app.models.schemas import TaskExecutionMode


class RecordingAgent:
    def __init__(self, result="EXACT output"):
        self.result = result
        self.calls = []

    async def run(self, directive, context):
        self.calls.append((directive, context))
        return self.result


def state(
    *,
    mode=TaskExecutionMode.FIXED,
    route=None,
    completed=(),
):
    return GraphRunState(
        task_id="T-node",
        workspace_id="WS-test",
        user_id="USR-test",
        context=ExecutionContext(
            original_directive="ORIGINAL directive",
            execution_mode=mode,
            route=route,
        ),
        current_agent=None,
        completed_agents=completed,
        final_output=None,
    )


def apply_update(original, update):
    return GraphRunState(**{**original, **update})


def test_registry_contains_only_current_executable_contract_agents():
    assert set(GRAPH_NODES) == {
        "research",
        "data",
        "analysis",
        "summarizer",
        "report",
        "direct",
    }
    assert "web_search" not in GRAPH_NODES


@pytest.mark.asyncio
async def test_node_calls_existing_agent_run_with_authoritative_context():
    agent = RecordingAgent("Research result")
    node = make_agent_node("research", agent=agent)
    original = state()

    update = await node(original)

    assert agent.calls == [
        ("ORIGINAL directive", original["context"])
    ]
    assert update["context"].output("research_findings").text == "Research result"
    assert update["completed_agents"] == ("research",)
    assert update["current_agent"] == "research"
    assert update["final_output"] == "Research result"

    assert original["context"].available_outputs == ()
    assert original["completed_agents"] == ()


@pytest.mark.asyncio
async def test_sequential_nodes_preserve_exact_output_provenance():
    research = RecordingAgent("EXACT research\nwith uncertainty")
    analysis = RecordingAgent("EXACT analysis\nwith caveat")

    first = state()
    first_update = await make_agent_node("research", agent=research)(first)
    second = apply_update(first, first_update)

    second_update = await make_agent_node("analysis", agent=analysis)(second)
    final = apply_update(second, second_update)

    assert analysis.calls[0][1].output("research_findings").text == (
        "EXACT research\nwith uncertainty"
    )
    assert final["context"].output("research_findings").text == (
        "EXACT research\nwith uncertainty"
    )
    assert final["context"].output("insights").text == (
        "EXACT analysis\nwith caveat"
    )
    assert final["completed_agents"] == ("research", "analysis")
    assert final["final_output"] == "EXACT analysis\nwith caveat"


@pytest.mark.asyncio
async def test_adaptive_skipped_agent_cannot_create_output():
    route = RouteSelection(
        selected_agents=("research", "analysis", "report"),
        skipped_agents=("data", "summarizer"),
    )
    original = state(
        mode=TaskExecutionMode.ADAPTIVE,
        route=route,
    )

    data = RecordingAgent("Should not become graph state")
    node = make_agent_node("data", agent=data)

    with pytest.raises(Exception):
        await node(original)

    assert original["context"].available_outputs == ()
    assert original["completed_agents"] == ()


@pytest.mark.asyncio
async def test_duplicate_graph_agent_execution_is_rejected_before_agent_call():
    agent = RecordingAgent("duplicate")
    node = make_agent_node("research", agent=agent)
    original = state(completed=("research",))

    with pytest.raises(ValueError, match="already completed"):
        await node(original)

    assert agent.calls == []


@pytest.mark.asyncio
async def test_empty_agent_result_is_rejected_without_fabricated_output():
    agent = RecordingAgent("   ")
    node = make_agent_node("research", agent=agent)
    original = state()

    with pytest.raises(ValueError, match="empty output"):
        await node(original)

    assert original["context"].available_outputs == ()
    assert original["final_output"] is None


def test_unknown_graph_agent_cannot_be_wrapped():
    with pytest.raises(ValueError, match="Unknown executable graph agent"):
        make_agent_node("web_search")
