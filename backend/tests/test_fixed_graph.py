import unittest

from app.agents.execution_context import ExecutionContext
from app.agents.graph_nodes import make_agent_node
from app.agents.graph_state import GraphRunState
from app.agents.graphs import build_fixed_graph
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


def initial_state():
    return GraphRunState(
        task_id="T-fixed",
        workspace_id="WS-test",
        user_id="USR-test",
        context=ExecutionContext(
            original_directive="ORIGINAL fixed directive",
            execution_mode=TaskExecutionMode.FIXED,
        ),
        current_agent=None,
        completed_agents=(),
        final_output=None,
    )


class FixedGraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_fixed_graph_runs_exact_five_stage_order(self):
        order = []

        research = RecordingAgent("research", "R", order)
        data = RecordingAgent("data", "D", order)
        analysis = RecordingAgent("analysis", "A", order)
        summarizer = RecordingAgent("summarizer", "S", order)
        report = RecordingAgent("report", "FINAL", order)

        graph = build_fixed_graph(
            research=make_agent_node("research", agent=research),
            data=make_agent_node("data", agent=data),
            analysis=make_agent_node("analysis", agent=analysis),
            summarizer=make_agent_node("summarizer", agent=summarizer),
            report=make_agent_node("report", agent=report),
        )

        result = await graph.ainvoke(initial_state())

        self.assertEqual(
            order,
            ["research", "data", "analysis", "summarizer", "report"],
        )

        self.assertEqual(
            result["completed_agents"],
            ("research", "data", "analysis", "summarizer", "report"),
        )

        self.assertEqual(result["current_agent"], "report")
        self.assertEqual(result["final_output"], "FINAL")

    async def test_fixed_graph_preserves_exact_handoff_outputs(self):
        order = []

        research = RecordingAgent("research", "EXACT research\n", order)
        data = RecordingAgent("data", "EXACT data\n", order)
        analysis = RecordingAgent("analysis", "EXACT analysis\n", order)
        summarizer = RecordingAgent("summarizer", "EXACT summary\n", order)
        report = RecordingAgent("report", "EXACT final\n", order)

        graph = build_fixed_graph(
            research=make_agent_node("research", agent=research),
            data=make_agent_node("data", agent=data),
            analysis=make_agent_node("analysis", agent=analysis),
            summarizer=make_agent_node("summarizer", agent=summarizer),
            report=make_agent_node("report", agent=report),
        )

        result = await graph.ainvoke(initial_state())
        context = result["context"]

        self.assertEqual(
            context.output("research_findings").text,
            "EXACT research\n",
        )
        self.assertEqual(
            context.output("structured_data").text,
            "EXACT data\n",
        )
        self.assertEqual(
            context.output("insights").text,
            "EXACT analysis\n",
        )
        self.assertEqual(
            context.output("summary").text,
            "EXACT summary\n",
        )
        self.assertEqual(
            context.output("final_report").text,
            "EXACT final\n",
        )

        self.assertEqual(result["final_output"], "EXACT final\n")

    async def test_fixed_graph_stops_on_stage_failure(self):
        order = []

        research = RecordingAgent("research", "R", order)

        class FailingDataAgent:
            async def run(self, directive, context):
                order.append("data")
                raise RuntimeError("data failed")

        analysis = RecordingAgent("analysis", "A", order)
        summarizer = RecordingAgent("summarizer", "S", order)
        report = RecordingAgent("report", "FINAL", order)

        graph = build_fixed_graph(
            research=make_agent_node("research", agent=research),
            data=make_agent_node("data", agent=FailingDataAgent()),
            analysis=make_agent_node("analysis", agent=analysis),
            summarizer=make_agent_node("summarizer", agent=summarizer),
            report=make_agent_node("report", agent=report),
        )

        with self.assertRaisesRegex(RuntimeError, "data failed"):
            await graph.ainvoke(initial_state())

        self.assertEqual(order, ["research", "data"])


if __name__ == "__main__":
    unittest.main()
