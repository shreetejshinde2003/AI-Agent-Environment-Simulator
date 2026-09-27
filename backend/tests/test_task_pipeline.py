"""Focused tests for the in-process multi-agent task coordinator.

These tests replace agents and event writers with fakes. They never call
Groq, open a WebSocket, or require a running FastAPI server.
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.api.routes import tasks
from app.models.schemas import Task, TaskExecutionMode, TaskPriority, TaskStatus


class FakeAgent:
    def __init__(self, agent_id: str, result: str | Exception, call_order: list[str]):
        self.agent_id = agent_id
        self.result = result
        self.call_order = call_order
        self.calls: list[tuple[str, dict]] = []

    async def run(self, directive: str, context: dict | None = None) -> str:
        self.call_order.append(self.agent_id)
        self.calls.append((directive, dict(context or {})))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class TaskPipelineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.call_order: list[str] = []
        self.research = FakeAgent("research", "research result", self.call_order)
        self.data = FakeAgent("data", "structured result", self.call_order)
        self.analysis = FakeAgent("analysis", "analysis result", self.call_order)
        self.summarizer = FakeAgent("summarizer", "summary result", self.call_order)
        self.report = FakeAgent("report", "final report", self.call_order)
        self.web_search = FakeAgent("web_search", "must not run", self.call_order)
        self.agent_mapping = {
            "research": self.research,
            "data": self.data,
            "analysis": self.analysis,
            "summarizer": self.summarizer,
            "report": self.report,
            "web_search": self.web_search,
        }

        self.broadcast = AsyncMock()
        self.activity = AsyncMock()
        self.message = AsyncMock()
        self.finished = AsyncMock()
        self.patches = [
            patch.object(tasks, "_IMPLEMENTED_AGENTS", self.agent_mapping),
            patch.object(tasks.manager, "broadcast", self.broadcast),
            patch.object(tasks, "record_activity", self.activity),
            patch.object(tasks, "record_message", self.message),
            patch.object(tasks, "register_task_finished", self.finished),
        ]
        for active_patch in self.patches:
            active_patch.start()
        tasks._TASKS.clear()

    def tearDown(self):
        tasks._TASKS.clear()
        for active_patch in reversed(self.patches):
            active_patch.stop()

    def make_task(self, execution_mode: TaskExecutionMode, agent_id: str = "orchestrator") -> Task:
        task = Task(
            id="T-test",
            directive="Compare HR retention approaches",
            assigned_agent_id=agent_id,
            execution_mode=execution_mode,
            status=TaskStatus.QUEUED,
            priority=TaskPriority.MEDIUM,
            started_at=datetime.now(timezone.utc),
            duration_seconds=0,
            progress_percent=0,
            progress_steps=[],
        )
        tasks._TASKS[task.id] = task
        return task

    async def test_pipeline_passes_each_real_stage_output_to_the_next_stage(self):
        task = self.make_task(TaskExecutionMode.FULL_PIPELINE)

        await tasks._run_task(task.id)

        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.output, "final report")
        self.assertEqual(
            self.call_order,
            ["research", "data", "analysis", "summarizer", "report"],
        )
        self.assertEqual(self.research.calls[0][1], {})
        self.assertEqual(self.data.calls[0][1], {"research_findings": "research result"})
        self.assertEqual(
            self.analysis.calls[0][1],
            {"research_findings": "research result", "structured_data": "structured result"},
        )
        self.assertEqual(
            self.summarizer.calls[0][1]["insights"],
            "analysis result",
        )
        self.assertEqual(self.report.calls[0][1]["summary"], "summary result")
        self.assertEqual(self.web_search.calls, [])

        self.assertEqual(self.message.await_count, 4)
        handoffs = [call.args[:2] for call in self.message.await_args_list]
        self.assertEqual(
            handoffs,
            [
                ("research", "data"),
                ("data", "analysis"),
                ("analysis", "summarizer"),
                ("summarizer", "report"),
            ],
        )
        self.assertGreaterEqual(self.activity.await_count, 11)
        self.assertTrue(any(call.args[0] == "task_updated" for call in self.broadcast.await_args_list))
        self.finished.assert_awaited_once()
        self.assertTrue(self.finished.await_args.kwargs["success"])

    async def test_pipeline_failure_stops_downstream_agents(self):
        self.data.result = RuntimeError("data stage unavailable")
        task = self.make_task(TaskExecutionMode.FULL_PIPELINE)

        await tasks._run_task(task.id)

        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertEqual(task.error, "data stage unavailable")
        self.assertIsNone(task.output)
        self.assertEqual(len(self.research.calls), 1)
        self.assertEqual(len(self.data.calls), 1)
        self.assertEqual(self.call_order, ["research", "data"])
        self.assertEqual(self.analysis.calls, [])
        self.assertEqual(self.summarizer.calls, [])
        self.assertEqual(self.report.calls, [])
        self.assertEqual(self.web_search.calls, [])
        self.assertEqual(self.message.await_count, 1)
        self.finished.assert_awaited_once()
        self.assertFalse(self.finished.await_args.kwargs["success"])

    async def test_direct_agent_mode_remains_a_single_agent_execution(self):
        task = self.make_task(TaskExecutionMode.SINGLE_AGENT, agent_id="analysis")

        await tasks._run_task(task.id)

        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.output, "analysis result")
        self.assertEqual(self.call_order, ["analysis"])
        self.assertEqual(self.analysis.calls, [(task.directive, {})])
        self.assertEqual(self.research.calls, [])
        self.assertEqual(self.data.calls, [])
        self.assertEqual(self.summarizer.calls, [])
        self.assertEqual(self.report.calls, [])
        self.assertEqual(self.message.await_count, 0)


if __name__ == "__main__":
    unittest.main()
