import unittest

from app.agents.execution_context import ExecutionContext, RouteSelection
from app.agents.graph_nodes import make_agent_node
from app.agents.graph_state import GraphRunState
from app.agents.graphs import build_adaptive_graph
from app.models.schemas import TaskExecutionMode


class RecordingAgent:
    def __init__(self, agent_id, output, order):
        self.agent_id = agent_id
        self.output = output
        self.order = order
        self.calls = []

    async def run(self, directive, context):
        self.order.append(self.agent_id)
        self.calls.append((directive, context))
        return self.output


def initial_state(selected, skipped, *, completed=()):
    return GraphRunState(
        task_id="T-adaptive",
        workspace_id="WS-test",
        user_id="USR-test",
        context=ExecutionContext(
            original_directive="ORIGINAL adaptive directive",
            execution_mode=TaskExecutionMode.ADAPTIVE,
            route=RouteSelection(
                selected_agents=selected,
                skipped_agents=skipped,
            ),
        ),
        current_agent=None,
        completed_agents=completed,
        final_output=None,
    )


def graph_with_recorders(order):
    agents = {
        "research": RecordingAgent("research", "R", order),
        "data": RecordingAgent("data", "D", order),
        "analysis": RecordingAgent("analysis", "A", order),
        "summarizer": RecordingAgent("summarizer", "S", order),
        "report": RecordingAgent("report", "FINAL", order),
    }

    graph = build_adaptive_graph(
        research=make_agent_node("research", agent=agents["research"]),
        data=make_agent_node("data", agent=agents["data"]),
        analysis=make_agent_node("analysis", agent=agents["analysis"]),
        summarizer=make_agent_node("summarizer", agent=agents["summarizer"]),
        report=make_agent_node("report", agent=agents["report"]),
    )

    return graph, agents


class AdaptiveGraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_executes_only_selected_route_in_order(self):
        order = []
        graph, agents = graph_with_recorders(order)

        result = await graph.ainvoke(
            initial_state(
                ("data", "analysis", "report"),
                ("research", "summarizer"),
            )
        )

        self.assertEqual(order, ["data", "analysis", "report"])
        self.assertEqual(
            result["completed_agents"],
            ("data", "analysis", "report"),
        )
        self.assertEqual(result["current_agent"], "report")
        self.assertEqual(result["final_output"], "FINAL")

        self.assertEqual(agents["research"].calls, [])
        self.assertEqual(agents["summarizer"].calls, [])

        self.assertEqual(
            result["context"].available_outputs,
            ("structured_data", "insights", "final_report"),
        )

    async def test_report_only_route_executes_report_once(self):
        order = []
        graph, agents = graph_with_recorders(order)

        result = await graph.ainvoke(
            initial_state(
                ("report",),
                ("research", "data", "analysis", "summarizer"),
            )
        )

        self.assertEqual(order, ["report"])
        self.assertEqual(result["completed_agents"], ("report",))
        self.assertEqual(result["final_output"], "FINAL")

        for agent_id in ("research", "data", "analysis", "summarizer"):
            self.assertEqual(agents[agent_id].calls, [])

    async def test_selected_handoffs_preserve_exact_outputs(self):
        order = []

        research = RecordingAgent("research", "EXACT research\n", order)
        analysis = RecordingAgent("analysis", "EXACT analysis\n", order)
        report = RecordingAgent("report", "EXACT report\n", order)

        unused_data = RecordingAgent("data", "SHOULD NOT RUN", order)
        unused_summarizer = RecordingAgent(
            "summarizer",
            "SHOULD NOT RUN",
            order,
        )

        graph = build_adaptive_graph(
            research=make_agent_node("research", agent=research),
            data=make_agent_node("data", agent=unused_data),
            analysis=make_agent_node("analysis", agent=analysis),
            summarizer=make_agent_node(
                "summarizer",
                agent=unused_summarizer,
            ),
            report=make_agent_node("report", agent=report),
        )

        result = await graph.ainvoke(
            initial_state(
                ("research", "analysis", "report"),
                ("data", "summarizer"),
            )
        )

        context = result["context"]

        self.assertEqual(order, ["research", "analysis", "report"])
        self.assertEqual(
            context.output("research_findings").text,
            "EXACT research\n",
        )
        self.assertEqual(
            context.output("insights").text,
            "EXACT analysis\n",
        )
        self.assertEqual(
            context.output("final_report").text,
            "EXACT report\n",
        )

        self.assertEqual(unused_data.calls, [])
        self.assertEqual(unused_summarizer.calls, [])

    async def test_missing_route_is_rejected_before_agent_execution(self):
        order = []
        graph, agents = graph_with_recorders(order)

        state = GraphRunState(
            task_id="T-adaptive",
            workspace_id="WS-test",
            user_id="USR-test",
            context=ExecutionContext(
                original_directive="ORIGINAL adaptive directive",
                execution_mode=TaskExecutionMode.ADAPTIVE,
            ),
            current_agent=None,
            completed_agents=(),
            final_output=None,
        )

        with self.assertRaisesRegex(ValueError, "requires a selected route"):
            await graph.ainvoke(state)

        self.assertEqual(order, [])
        for agent in agents.values():
            self.assertEqual(agent.calls, [])

    async def test_tampered_route_prefix_is_rejected(self):
        order = []
        graph, agents = graph_with_recorders(order)

        state = initial_state(
            ("data", "analysis", "report"),
            ("research", "summarizer"),
            completed=("analysis",),
        )

        with self.assertRaisesRegex(ValueError, "selected route prefix"):
            await graph.ainvoke(state)

        self.assertEqual(order, [])
        for agent in agents.values():
            self.assertEqual(agent.calls, [])

    async def test_invalid_selected_skipped_partition_is_rejected(self):
        order = []
        graph, agents = graph_with_recorders(order)

        state = initial_state(
            ("analysis", "report"),
            ("research", "data", "summarizer"),
        )

        state["context"] = state["context"].model_copy(
            update={
                "route": RouteSelection(
                    selected_agents=("analysis", "report"),
                    skipped_agents=("research", "data"),
                )
            }
        )

        with self.assertRaisesRegex(ValueError, "exact partition"):
            await graph.ainvoke(state)

        self.assertEqual(order, [])
        for agent in agents.values():
            self.assertEqual(agent.calls, [])


if __name__ == "__main__":
    unittest.main()
