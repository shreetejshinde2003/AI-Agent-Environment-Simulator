import unittest

from app.agents.execution_context import ExecutionContext
from app.agents.graph_nodes import make_agent_node
from app.agents.graph_state import GraphRunState
from app.agents.graphs import build_single_graph
from app.models.schemas import TaskExecutionMode


class RecordingAgent:
    def __init__(self, result="EXACT direct answer"):
        self.result = result
        self.calls = []

    async def run(self, directive, context):
        self.calls.append((directive, context))
        return self.result


def initial_state():
    return GraphRunState(
        task_id="T-single",
        workspace_id="WS-test",
        user_id="USR-test",
        context=ExecutionContext(
            original_directive="ORIGINAL single directive",
            execution_mode=TaskExecutionMode.SINGLE,
        ),
        current_agent=None,
        completed_agents=(),
        final_output=None,
    )


class SingleGraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_graph_runs_only_direct_agent(self):
        agent = RecordingAgent()
        direct = make_agent_node("direct", agent=agent)
        graph = build_single_graph(node=direct)
        original = initial_state()

        result = await graph.ainvoke(original)

        self.assertEqual(len(agent.calls), 1)
        self.assertEqual(
            agent.calls[0],
            ("ORIGINAL single directive", original["context"]),
        )

        self.assertEqual(result["current_agent"], "direct")
        self.assertEqual(result["completed_agents"], ("direct",))
        self.assertEqual(result["final_output"], "EXACT direct answer")

        output = result["context"].output("final_answer")
        self.assertIsNotNone(output)
        self.assertEqual(output.agent_id, "direct")
        self.assertEqual(output.text, "EXACT direct answer")

        self.assertEqual(result["task_id"], "T-single")
        self.assertEqual(result["workspace_id"], "WS-test")
        self.assertEqual(result["user_id"], "USR-test")

    async def test_single_graph_preserves_exact_direct_output(self):
        agent = RecordingAgent("Line one\nLine two\n")
        graph = build_single_graph(
            node=make_agent_node("direct", agent=agent)
        )

        result = await graph.ainvoke(initial_state())

        self.assertEqual(result["final_output"], "Line one\nLine two\n")
        self.assertEqual(
            result["context"].output("final_answer").text,
            "Line one\nLine two\n",
        )

    async def test_single_graph_propagates_agent_failure_without_fabricated_state(self):
        class FailingAgent:
            async def run(self, directive, context):
                raise RuntimeError("provider unavailable")

        graph = build_single_graph(
            node=make_agent_node("direct", agent=FailingAgent())
        )
        original = initial_state()

        with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
            await graph.ainvoke(original)

        self.assertEqual(original["completed_agents"], ())
        self.assertIsNone(original["final_output"])
        self.assertEqual(original["context"].available_outputs, ())


if __name__ == "__main__":
    unittest.main()
