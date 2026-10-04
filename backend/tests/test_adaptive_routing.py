"""No live LLM calls: deterministic planning and real lifecycle/persistence."""
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient

from app.agents.execution_context import ExecutionContext
from app.agents.routing import plan_route, validate_route, inline_source, SPECIALISTS
from app.api.routes import tasks
from app.api.routes.uploads import parse_upload
from app.main import app
from app.models.schemas import CreateTaskRequest, Task, display_title
from app.storage.database import repository, Repository
import test_task_pipeline as pipeline_support


class RoutingTests(unittest.TestCase):
    def context(self, directive="Analyze tradeoffs", **kwargs):
        return ExecutionContext(original_directive=directive, execution_mode="adaptive", **kwargs)

    def test_representative_categories_and_exact_order(self):
        cases = [
            ("Summarize this", {"uploaded_context": "Real source."}, (), ("summarizer", "report")),
            ("Extract fields", {"uploaded_context": "a=1"}, (), ("data", "report")),
            ("Analyze tradeoffs", {}, (), ("analysis", "report")),
            ("Compare departments", {"benchmark_context": "Department counts"}, (), ("data", "analysis", "report")),
            ("Describe patterns", {"uploaded_context": "a,b\n1,2"}, ("csv",), ("data", "analysis", "report")),
            ("Explain REST", {}, (), ("research", "report")),
            ("Research and analyze REST", {}, (), ("research", "analysis", "report")),
            ("Research and summarize REST", {}, (), ("research", "summarizer", "report")),
            ("Write a report", {}, (), ("report",)),
        ]
        for directive, data, formats, selected in cases:
            with self.subTest(directive=directive):
                plan = plan_route(self.context(directive, **data), formats)
                self.assertEqual(plan.selected_agent_ids, selected)
                self.assertEqual(plan.validation_status, "valid")
                self.assertEqual(set(plan.skipped_agent_ids), set(SPECIALISTS) - set(selected))

    def test_normalization_and_source_is_not_a_routing_instruction(self):
        one = plan_route(self.context("  COMPARE   departments ", uploaded_context="Summarize and research"), ("json",))
        two = plan_route(self.context("compare departments", uploaded_context="Other content"), ("json",))
        self.assertEqual(one, two)
        inline = "Summarize\nSource: Research and analyze are words in this source."
        source = inline_source(inline)
        plan = plan_route(self.context(inline, source_text=source))
        self.assertEqual(plan.selected_agent_ids, ("summarizer", "report"))

    def test_explicit_category_override_and_unknown_rejection(self):
        plan = plan_route(self.context("Research this", task_type="  Reporting  "))
        self.assertEqual(plan.selected_agent_ids, ("report",))
        with self.assertRaisesRegex(ValueError, "Unsupported adaptive taskType"):
            plan_route(self.context(task_type="made_up"))

    def test_invalid_routes_rejected_without_fake_dependency_artifacts(self):
        context = self.context("Summarize this")
        plan = plan_route(context)
        self.assertEqual(plan.validation_status, "invalid")
        self.assertIn("source material", plan.validation_error)
        self.assertEqual(context.prior_outputs, ())
        good = plan_route(self.context())
        for changes in (
            {"selected_agent_ids": ("web_search", "report")},
            {"selected_agent_ids": ("direct", "report")},
            {"selected_agent_ids": ("analysis", "analysis", "report")},
            {"selected_agent_ids": ("analysis",)},
            {"skipped_agent_ids": ()},
            {"required_capabilities": ("unavailable",)},
            {"available_inputs": ()},
        ):
            self.assertEqual(validate_route(good.model_copy(update=changes), self.context()).validation_status, "invalid")

    def test_title_is_deterministic_and_bounded(self):
        self.assertEqual(display_title("  Explain\nREST  APIs "), "Explain REST APIs")
        self.assertEqual(display_title("Goal", "Team run"), "Team run")
        self.assertLessEqual(len(display_title("word " * 50)), 80)


# Reuse isolated database/agent setup, not inherited regression test methods.
class AdaptiveExecutionTests(unittest.IsolatedAsyncioTestCase):
    setUp = pipeline_support.PipelineTests.setUp
    tearDown = pipeline_support.PipelineTests.tearDown
    authenticate_client = pipeline_support.PipelineTests.authenticate_client

    async def create(self, directive="Analyze supplied data", **kwargs):
        upload = parse_upload("table.csv", b"department,count\nEngineering,4")
        repository.save_upload(upload)
        return await tasks.create_task(CreateTaskRequest(directive=directive, execution_mode="adaptive",
                                      upload_ids=[upload.id], **kwargs), BackgroundTasks())

    async def test_selected_stages_handoffs_events_metrics_and_restart(self):
        queued = await self.create()
        self.assertEqual(queued.route_plan.selected_agent_ids, ("data", "analysis", "report"))
        self.assertEqual(queued.agent_invocation_count, 0)
        await tasks._run_task(queued.id)
        run = repository.get(queued.id)
        self.assertEqual(self.order, ["data", "analysis", "report"])
        self.assertEqual(run.output, "report actual output")
        self.assertEqual(run.agent_invocation_count, 3)
        self.assertEqual(run.handoff_count, 2)
        self.assertEqual([(m.from_agent_id, m.to_agent_id) for m in run.messages],
                         [("data", "analysis"), ("analysis", "report")])
        self.assertEqual(self.agents["research"].calls, [])
        self.assertEqual(self.agents["summarizer"].calls, [])
        self.assertEqual(self.direct_agent.calls, [])
        self.assertEqual(self.agents["analysis"].calls[0][1]["structured_data"], "data actual output")
        self.assertEqual(self.agents["report"].calls[0][1]["insights"], "analysis actual output")
        self.assertEqual([e.agent_id for e in run.events if e.type == "agent_started"], self.order)
        self.assertEqual([e.type for e in run.events], ["simulation_created", "route_planned", "simulation_started",
            "agent_started", "agent_completed", "message_created", "agent_started", "agent_completed",
            "message_created", "agent_started", "agent_completed", "simulation_completed"])
        updates = [call.args[1] for call in self.broadcast.await_args_list if call.args[0] == "task_updated"]
        self.assertEqual(updates[-1]["routePlan"]["selectedAgentIds"], ["data", "analysis", "report"])
        reopened = Repository("sqlite:///" + self.path)
        reopened.initialize()
        self.assertEqual(reopened.get(run.id).route_plan, run.route_plan)
        self.assertEqual(reopened.get(run.id).title, run.title)
        self.assertEqual(reopened.get(run.id).agent_invocation_count, 3)

    async def test_real_specialist_prompts_and_accounting_with_mocked_provider(self):
        from app.agents.data_agent import DataAgent
        from app.agents.analysis_agent import AnalysisAgent
        from app.agents.report_agent import ReportAgent
        from app.agents.llm_client import LLMResponse
        provider = AsyncMock(return_value=LLMResponse(text="Grounded fixture", model="test-model",
                                                      input_tokens=4, output_tokens=2, response_time_seconds=0.01))
        with patch.object(tasks, "_IMPLEMENTED_AGENTS", {"data": DataAgent(), "analysis": AnalysisAgent(), "report": ReportAgent()}), \
             patch("app.agents.data_agent.call_llm", provider), \
             patch("app.agents.analysis_agent.call_llm", provider), \
             patch("app.agents.report_agent.call_llm", provider):
            queued = await self.create()
            await tasks._run_task(queued.id)
        run = repository.get(queued.id)
        self.assertEqual(run.status.value, "completed", run.error)
        self.assertEqual(provider.await_count, 3)
        self.assertEqual(run.output, "Grounded fixture")
        for call in provider.await_args_list:
            self.assertIn("Analyze supplied data", call.kwargs["prompt"])
        self.assertIn("structured_data", provider.await_args_list[1].kwargs["prompt"])
        self.assertIn("insights", provider.await_args_list[2].kwargs["prompt"])
        self.assertEqual(sum(s.total_tokens for s in run.stages), 18)

    async def test_failure_stops_selected_downstream_and_persists(self):
        self.agents["analysis"].failure = "Controlled test failure"
        queued = await self.create()
        await tasks._run_task(queued.id)
        run = repository.get(queued.id)
        self.assertEqual(self.order, ["data", "analysis"])
        self.assertEqual([s.status for s in run.stages], ["completed", "failed", "waiting"])
        self.assertEqual(run.status.value, "failed")
        self.assertEqual(run.error, "Controlled test failure")
        self.assertIsNone(run.output)
        self.assertEqual(run.handoff_count, 1)
        self.assertEqual(run.agent_invocation_count, 2)

    async def test_tampered_plan_or_stages_fail_before_any_model_call(self):
        queued = await self.create()
        tasks._TASKS[queued.id].stages.reverse()
        await tasks._run_task(queued.id)
        run = repository.get(queued.id)
        self.assertEqual(self.order, [])
        self.assertEqual(run.status.value, "failed")
        self.assertIn("do not match", run.error)

    async def test_invalid_request_has_no_created_run_or_calls(self):
        with self.assertRaises(HTTPException) as caught:
            await tasks.create_task(CreateTaskRequest(directive="Summarize", execution_mode="adaptive"), BackgroundTasks())
        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(repository.list(), [])
        self.assertEqual(self.order, [])

    async def test_api_exports_and_legacy_snapshot(self):
        with TestClient(app) as client:
            self.authenticate_client(client)
            response = client.post("/api/v1/simulations", json={"directive": "Summarize\nSource: Two tests passed.",
                                   "executionMode": "adaptive", "title": "Test results"})
            self.assertEqual(response.status_code, 201, response.text)
            run = client.get("/api/v1/tasks/" + response.json()["id"]).json()
            self.assertEqual(run["title"], "Test results")
            self.assertEqual(run["routePlan"]["selectedAgentIds"], ["summarizer", "report"])
            self.assertEqual(run["agentInvocationCount"], 2)
            self.assertEqual(run["taskType"], "summarization")
            for format in ("json", "txt", "csv"):
                export = client.get(f'/api/v1/simulations/{run["id"]}/export?format={format}')
                self.assertEqual(export.status_code, 200)
            for body in ({"taskType": "wrong"}, {"executionMode": "bad"}, {"directive": " "}):
                bad = client.post("/api/v1/simulations", json={"directive": "Analyze", "executionMode": "adaptive", **body})
                self.assertEqual(bad.status_code, 422)
            legacy = {k: v for k, v in run.items() if k not in ("title", "routePlan", "agentInvocationCount", "handoffCount")}
            legacy["executionMode"] = "fixed"
            self.assertIsNone(Task.model_validate(legacy).route_plan)
            self.assertTrue(Task.model_validate(legacy).title)

    async def test_private_dataset_directory_registry_api_and_safe_context(self):
        import shutil
        from pathlib import Path
        from app.datasets.registry import BENCHMARK_DIR, register_all, benchmark_directory
        from app.core.config import settings
        if not (BENCHMARK_DIR / "employee_small.json").exists():
            self.skipTest("Private files unavailable; dataset validation tests use synthetic fixtures")
        private_dir = Path(self.temp.name) / "private-benchmarks"
        private_dir.mkdir()
        for source in BENCHMARK_DIR.glob("*.json"):
            shutil.copyfile(source, private_dir / source.name)
        with patch.object(settings, "BENCHMARK_DATA_DIR", str(private_dir)):
            self.assertEqual(benchmark_directory(), private_dir.resolve())
            register_all(repository)
            with TestClient(app) as client:
                self.authenticate_client(client)
                registered = client.get("/api/v1/datasets").json()
                self.assertEqual(len(registered), 6)
            queued = await self.create(dataset_id="employee_small")
            await tasks._run_task(queued.id)
        context = self.agents["data"].calls[0][1]["benchmark_context"]
        for field in ("Age", "Gender", "EmployeeID", "EmployeeName", "ManagerID", "Salary", "PerformanceRating"):
            self.assertNotIn(field, context)
        self.assertLessEqual(len(context), 3500)
