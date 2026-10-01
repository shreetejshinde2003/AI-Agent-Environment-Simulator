"""Isolated coordinator/API tests; no Groq requests or user database writes."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlalchemy import update
from app.api.routes import tasks
from app.agents.direct_agent import DirectAgent
from app.agents.llm_client import LLMResponse
from app.agents.execution_context import ExecutionContext
from app.main import app
from app.models.schemas import CreateTaskRequest, TaskExecutionMode
from app.storage.database import repository, Repository
from app.storage import models as dbm

class FakeAgent:
    def __init__(self, name, order, failure=None):
        self.name, self.order, self.failure = name, order, failure
        self.calls = []
    async def run(self, directive, context=None):
        self.order.append(self.name)
        # Keep the regression assertions about exact flat handoffs while the
        # production boundary now supplies a typed, immutable context.
        if isinstance(context, ExecutionContext):
            assert context.original_directive == directive
            captured = {output.name: output.text for output in context.prior_outputs}
            captured.update({name: getattr(context, name) for name in
                             ("uploaded_context", "benchmark_context") if getattr(context, name) is not None})
        else:
            captured = dict(context or {})
        self.calls.append((directive, captured))
        if self.failure:
            raise RuntimeError(self.failure)
        return self.name + " actual output"

class PipelineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "test.db")
        self.path_patch = patch.object(repository, "path", self.path)
        self.path_patch.start()
        repository.initialize()
        self.order = []
        self.agents = {key: FakeAgent(key, self.order) for key, _ in tasks._PIPELINE_STAGES}
        self.direct_agent = FakeAgent("direct", self.order)
        self.agent_patch = patch.object(tasks, "_IMPLEMENTED_AGENTS",
                                        {**self.agents, "direct": self.direct_agent})
        self.agent_patch.start()
        self.broadcast = AsyncMock()
        self.socket_patch = patch.object(tasks.manager, "broadcast", self.broadcast)
        self.socket_patch.start()
    def tearDown(self):
        tasks._TASKS.clear()
        self.socket_patch.stop()
        self.agent_patch.stop()
        self.path_patch.stop()
        self.temp.cleanup()
    async def run_task(self, agent="orchestrator", mode="full_pipeline", uploads=None):
        queued = await tasks.create_task(CreateTaskRequest(
            directive="Original goal", assigned_agent_id=agent,
            execution_mode=mode, upload_ids=uploads or []), BackgroundTasks())
        await tasks._run_task(queued.id)
        return repository.get(queued.id)
    async def test_exact_handoffs_events_persistence(self):
        run = await self.run_task()
        self.assertEqual(self.order, list(self.agents))
        self.assertEqual(run.output, "report actual output")
        self.assertEqual(run.status.value, "completed")
        self.assertEqual(run.progress_percent, 100)
        self.assertEqual(len(run.messages), 4)
        for index, (aid, key) in enumerate(tasks._PIPELINE_STAGES):
            self.assertEqual(self.agents[aid].calls[0][0], "Original goal")
            if index < 4:
                next_id = tasks._PIPELINE_STAGES[index+1][0]
                self.assertEqual(self.agents[next_id].calls[0][1][key], run.stages[index].output)
                self.assertEqual(run.messages[index].content, run.stages[index].output)
        self.assertEqual(run.events[-1].type, "simulation_completed")
        self.assertEqual(sum(e.type == "agent_completed" for e in run.events), 5)
        self.assertGreaterEqual(len(run.activities), 11)
        self.assertTrue(all(s.total_tokens is None for s in run.stages))
        reopened = Repository("sqlite:///" + self.path)
        reopened.initialize()
        self.assertEqual(reopened.get(run.id).output, run.output)
        self.assertIn("task_updated", [c.args[0] for c in self.broadcast.await_args_list])
    async def test_failure_at_every_stage_stops_downstream(self):
        for index, aid in enumerate(self.agents):
            with self.subTest(agent=aid):
                self.order.clear()
                self.agents[aid].failure = "controlled failure"
                run = await self.run_task()
                self.assertEqual(self.order, list(self.agents)[:index+1])
                self.assertEqual(run.status.value, "failed")
                self.assertEqual(run.error, "controlled failure")
                self.assertIsNone(run.output)
                self.assertEqual([s.status for s in run.stages],
                                 ["completed"]*index + ["failed"] + ["waiting"]*(4-index))
                self.assertEqual(run.progress_percent, index*20)
                self.assertEqual(run.events[-1].type, "simulation_failed")
                self.agents[aid].failure = None
    async def test_input_contract_failure_is_persisted_without_provider_call(self):
        from app.agents import summarizer_agent
        tasks._IMPLEMENTED_AGENTS["summarizer"] = summarizer_agent.SummarizerAgent()
        queued = await tasks.create_task(CreateTaskRequest(
            directive="Original goal", assigned_agent_id="summarizer",
            execution_mode="single_agent"), BackgroundTasks())
        # Simulate a future selected route with no source; no adaptive route
        # is exposed through the HTTP API in this phase.
        missing_source = ExecutionContext(original_directive="Original goal",
                                          execution_mode=TaskExecutionMode.ADAPTIVE)
        with patch.object(tasks, "_prepared_context", return_value=missing_source), \
                patch.object(summarizer_agent, "call_llm", new_callable=AsyncMock) as llm:
            await tasks._run_task(queued.id)
        llm.assert_not_awaited()
        run = repository.get(queued.id)
        self.assertEqual(run.status.value, "failed")
        self.assertIsNone(run.output)
        self.assertEqual(run.stages[0].status, "failed")
        self.assertEqual(run.input_error.code, "missing_required_input")
        self.assertEqual(run.stages[0].input_error.agent_id, "summarizer")
        self.assertFalse(any(event.type == "message_created" for event in run.events))
        self.assertEqual(Repository("sqlite:///" + self.path).get(run.id).input_error.code,
                         "missing_required_input")
    async def test_direct_mode(self):
        # Historical specialist execution remains separate from the new baseline.
        run = await self.run_task("analysis", "single_agent")
        self.assertEqual(self.order, ["analysis"])
        self.assertEqual(run.output, "analysis actual output")
        self.assertEqual(run.messages, [])
    async def test_single_baseline_is_one_real_stage_with_no_handoffs(self):
        run = await self.run_task(mode="single")
        self.assertEqual(run.execution_mode, TaskExecutionMode.SINGLE)
        self.assertEqual(run.assigned_agent_id, "direct")
        self.assertEqual(self.order, ["direct"])
        self.assertEqual(self.direct_agent.calls, [("Original goal", {})])
        self.assertEqual(run.output, "direct actual output")
        self.assertEqual([(s.agent_id, s.output_key, s.status) for s in run.stages],
                         [("direct", "final_answer", "completed")])
        self.assertEqual(run.messages, [])
        self.assertEqual([e.type for e in run.events].count("agent_completed"), 1)
        self.assertEqual([e.type for e in run.events].count("message_created"), 0)
        self.assertFalse(any(e.agent_id == "orchestrator" for e in run.events))
        self.assertFalse(any(a.agent_id == "orchestrator" for a in run.activities))
        self.assertEqual([a.agent_id for a in run.activities if a.text == "Started processing"], ["direct"])
        reopened = Repository("sqlite:///" + self.path)
        reopened.initialize()
        self.assertEqual(reopened.get(run.id).execution_mode, TaskExecutionMode.SINGLE)
        self.assertEqual(reopened.get(run.id).output, run.output)
        stage_events = [c.args[1] for c in self.broadcast.await_args_list if c.args[0] == "agent_completed"]
        self.assertEqual(stage_events[0]["executionMode"], "single")
    async def test_single_failure_does_not_fabricate_success(self):
        self.direct_agent.failure = "controlled direct failure"
        run = await self.run_task(mode="single")
        self.assertEqual(self.order, ["direct"])
        self.assertEqual(run.status.value, "failed")
        self.assertEqual(run.error, "controlled direct failure")
        self.assertIsNone(run.output)
        self.assertEqual([s.status for s in run.stages], ["failed"])
        self.assertEqual(run.messages, [])
    async def test_mode_defaults_and_legacy_snapshot(self):
        self.assertEqual(CreateTaskRequest(directive="x", assigned_agent_id="research").execution_mode,
                         TaskExecutionMode.SINGLE_AGENT)
        from app.models.schemas import CreateSimulationRequest, Task
        self.assertEqual(CreateSimulationRequest(directive="x").execution_mode,
                         TaskExecutionMode.FIXED)
        self.assertIs(TaskExecutionMode.FULL_PIPELINE, TaskExecutionMode.FIXED)
        run = await self.run_task(mode="fixed")
        self.assertEqual(self.order, list(self.agents))
        self.assertEqual(run.execution_mode, TaskExecutionMode.FIXED)
        snapshot = run.model_dump(mode="json")
        snapshot["executionMode"] = "full_pipeline"
        self.assertEqual(Task.model_validate(snapshot).execution_mode, TaskExecutionMode.FIXED)
        with repository.engine.begin() as connection:
            connection.execute(update(dbm.simulations).where(dbm.simulations.c.id == run.id).values(
                execution_mode="full_pipeline", payload=snapshot))
        reopened = Repository("sqlite:///" + self.path)
        reopened.initialize()
        self.assertEqual(reopened.get(run.id).execution_mode, TaskExecutionMode.FIXED)
        self.assertEqual(reopened.get(run.id).output, run.output)
        snapshot.pop("executionMode")
        self.assertEqual(Task.model_validate(snapshot).execution_mode, TaskExecutionMode.SINGLE_AGENT)
    async def test_direct_agent_makes_one_shared_client_call_with_permitted_context(self):
        from app.agents import direct_agent
        response = LLMResponse(text="Actual direct answer", input_tokens=7,
                               output_tokens=4, response_time_seconds=0.1, model="test-model")
        with patch.object(direct_agent, "call_llm", new_callable=AsyncMock, return_value=response) as llm:
            actual = await DirectAgent().run("Original goal", {
                "uploaded_context": "File: reference.txt\nSafe note",
                "benchmark_context": "Records: 294; Department: Engineering"})
        self.assertEqual(actual, response.text)
        llm.assert_awaited_once()
        prompt = llm.await_args.kwargs["prompt"]
        self.assertEqual(prompt, "Original user directive:\nOriginal goal"
                         "\n\nPrepared uploaded reference context:\nFile: reference.txt\nSafe note"
                         "\n\nValidated benchmark aggregates (not individual records):\n"
                         "Records: 294; Department: Engineering")
    async def test_single_coordinator_records_real_model_usage(self):
        from app.agents import direct_agent

        tasks._IMPLEMENTED_AGENTS["direct"] = DirectAgent()

        response = LLMResponse(
            text="Actual direct answer",
            input_tokens=7,
            output_tokens=4,
            response_time_seconds=0.1,
            model="test-model",
        )

        with patch.object(
            direct_agent,
            "call_llm",
            new_callable=AsyncMock,
            return_value=response,
        ) as llm:
            run = await self.run_task(mode="single")

        llm.assert_awaited_once()

        self.assertEqual(run.output, response.text)
        self.assertEqual(len(run.stages), 1)
        self.assertEqual(run.stages[0].model, "test-model")
        self.assertEqual(
            (
                run.stages[0].input_tokens,
                run.stages[0].output_tokens,
                run.stages[0].total_tokens,
            ),
            (7, 4, 11),
        )
        self.assertEqual(run.messages, [])

    async def test_single_coordinator_preserves_missing_usage_as_null(self):
        from app.agents import direct_agent

        tasks._IMPLEMENTED_AGENTS["direct"] = DirectAgent()

        response = LLMResponse(
            text="Actual direct answer",
            input_tokens=None,
            output_tokens=None,
            response_time_seconds=0.1,
            model="test-model",
        )

        with patch.object(
            direct_agent,
            "call_llm",
            new_callable=AsyncMock,
            return_value=response,
        ) as llm:
            run = await self.run_task(mode="single")

        llm.assert_awaited_once()

        self.assertEqual(run.output, response.text)
        self.assertEqual(len(run.stages), 1)
        self.assertEqual(run.stages[0].model, "test-model")

        self.assertIsNone(run.stages[0].input_tokens)
        self.assertIsNone(run.stages[0].output_tokens)
        self.assertIsNone(run.stages[0].total_tokens)

        reopened = Repository("sqlite:///" + self.path)
        reopened.initialize()
        restored = reopened.get(run.id)

        self.assertIsNone(restored.stages[0].input_tokens)
        self.assertIsNone(restored.stages[0].output_tokens)
        self.assertIsNone(restored.stages[0].total_tokens)
    async def test_single_upload_context_uses_same_bounded_input(self):
        from app.api.routes.uploads import parse_upload
        upload = parse_upload("reference.txt", b"Supplied fact: 42")
        repository.save_upload(upload)
        run = await self.run_task(mode="single", uploads=[upload.id])
        self.assertEqual(run.uploads[0].id, upload.id)
        self.assertIn("File: reference.txt\nSupplied fact: 42",
                      self.direct_agent.calls[0][1]["uploaded_context"])
        self.assertEqual(run.messages, [])
    async def test_single_registered_benchmark_receives_only_safe_aggregates(self):
        from app.datasets.registry import BENCHMARK_DIR, register_all
        if not (BENCHMARK_DIR / "employee_small.json").is_file():
            self.skipTest("Private benchmark JSON files are not provisioned")
        register_all(repository)
        queued = await tasks.create_task(CreateTaskRequest(
            directive="Describe workforce structure", execution_mode="single",
            dataset_id="employee_small"), BackgroundTasks())
        await tasks._run_task(queued.id)
        run = repository.get(queued.id)
        context = self.direct_agent.calls[0][1]["benchmark_context"]
        self.assertEqual(run.dataset_id, "employee_small")
        self.assertIn("Records: 294", context)
        for excluded in ("EmployeeID", "Age", "Gender", "Salary", "PerformanceRating"):
            self.assertNotIn(excluded, context)
    async def test_api_mode_contract_and_invalid_adaptive_guard(self):
        with TestClient(app) as client:
            adaptive = client.post("/api/v1/simulations", json={
                "directive": "Summarize", "executionMode": "adaptive"})
            self.assertEqual(adaptive.status_code, 422)
            self.assertEqual(adaptive.json()["detail"]["code"], "invalid_route")
            self.assertEqual(repository.list(), [])
            malformed = client.post("/api/v1/simulations", json={
                "directive": "Original goal", "executionMode": "other"})
            self.assertEqual(malformed.status_code, 422)
            self.assertEqual(repository.list(), [])
            single = client.post("/api/v1/simulations", json={
                "directive": "Original goal", "executionMode": "single"})
            self.assertEqual(single.status_code, 201, single.text)
            task_id = single.json()["id"]
            self.assertEqual(single.json()["executionMode"], "single")
            result = client.get("/api/v1/simulations/" + task_id).json()
            self.assertEqual(result["executionMode"], "single")
            self.assertEqual([s["agentId"] for s in result["stages"]], ["direct"])
            self.assertEqual(result["messages"], [])
            self.assertEqual(client.get("/api/v1/tasks/" + task_id).json()["executionMode"], "single")
            metrics = client.get("/api/v1/simulations/metrics").json()
            self.assertEqual(metrics["history"][0]["executionMode"], "single")
            self.assertEqual(metrics["history"][0]["invocationCount"], 1)
            self.assertEqual(next(a for a in metrics["agents"] if a["agentId"] == "direct")["calls"], 1)
            self.assertEqual(client.get(f"/api/v1/simulations/{task_id}/export?format=json").json()["executionMode"], "single")
    async def test_web_search_and_orchestrator_not_executable(self):
        for aid in ("web_search", "orchestrator"):
            run = await self.run_task(aid, "single_agent")
            self.assertEqual(run.status.value, "failed")
            self.assertIn("not implemented", run.error)
        self.assertEqual(self.order, [])
    async def test_empty_output_is_failure(self):
        self.agents["research"].run = AsyncMock(return_value=" ")
        run = await self.run_task()
        self.assertEqual(run.status.value, "failed")
        self.assertIn("empty output", run.error)
        self.assertEqual(self.order, [])
    async def test_uploaded_context_is_used(self):
        from app.api.routes.uploads import parse_upload
        upload = parse_upload("reference.txt", b"Supplied fact: 42")
        repository.save_upload(upload)
        run = await self.run_task(uploads=[upload.id])
        self.assertIn("Supplied fact: 42", self.agents["research"].calls[0][1]["uploaded_context"])
        self.assertIn("Supplied fact: 42", self.agents["data"].calls[0][1]["uploaded_context"])
        self.assertEqual(run.uploads[0].id, upload.id)
    async def test_registered_benchmark_context_enters_real_pipeline(self):
        from app.datasets.registry import BENCHMARK_DIR, register_all
        if not (BENCHMARK_DIR / "employee_small.json").is_file():
            self.skipTest("Private benchmark JSON files are not provisioned")
        register_all(repository)
        queued = await tasks.create_task(CreateTaskRequest(
            directive="Summarize workforce structure", assigned_agent_id="orchestrator",
            execution_mode="full_pipeline", dataset_id="employee_small",
            task_type="descriptive_summary"), BackgroundTasks())
        await tasks._run_task(queued.id)
        run = repository.get(queued.id)
        self.assertEqual(run.dataset_id, "employee_small")
        self.assertEqual(run.task_type, "descriptive_summary")
        self.assertEqual(run.output, "report actual output")
        for agent in self.agents.values():
            self.assertIn("Records: 294", agent.calls[0][1]["benchmark_context"])
        self.assertNotIn("EmployeeID", self.agents["research"].calls[0][1]["benchmark_context"])
        self.assertEqual(self.agents["data"].calls[0][1]["research_findings"], "research actual output")
    async def test_dataset_http_contract_uses_camel_case(self):
        from app.datasets.registry import BENCHMARK_DIR, register_all
        if not (BENCHMARK_DIR / "hr_small.json").is_file():
            self.skipTest("Private benchmark JSON files are not provisioned")
        register_all(repository)
        with TestClient(app) as client:
            listed = client.get("/api/v1/datasets")
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(len(listed.json()), 6)
            self.assertIn("datasetId", listed.json()[0])
            self.assertIn("recordCount", listed.json()[0])
            self.assertNotIn("dataset_id", listed.json()[0])
            response = client.post("/api/v1/tasks", json={
                "directive": "Summarize workforce structure", "assignedAgentId": "orchestrator",
                "executionMode": "full_pipeline", "datasetId": "hr_small",
                "taskType": "descriptive_summary"})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["datasetId"], "hr_small")
            self.assertEqual(response.json()["taskType"], "descriptive_summary")
            self.assertEqual(repository.get(response.json()["id"]).output, "report actual output")
            missing = client.post("/api/v1/tasks", json={
                "directive": "No such dataset", "assignedAgentId": "research",
                "datasetId": "unknown_large"})
            self.assertEqual(missing.status_code, 404)
    async def test_restart_marks_interrupted_not_successful(self):
        queued = await tasks.create_task(CreateTaskRequest(directive="Interrupted",
            assigned_agent_id="research"), BackgroundTasks())
        tasks.recover_interrupted()
        run = repository.get(queued.id)
        self.assertEqual(run.status.value, "failed")
        self.assertIsNone(run.output)
        self.assertEqual(run.stages[0].status, "waiting")

    async def test_restart_preserves_completed_stages_and_marks_active_failed(self):
        queued = await tasks.create_task(CreateTaskRequest(directive="Interrupted pipeline",
            assigned_agent_id="orchestrator", execution_mode="full_pipeline"), BackgroundTasks())
        run = repository.get(queued.id)
        run.status = tasks.TaskStatus.IN_PROGRESS
        run.execution_started_at = tasks.now()
        run.stages[0].status = "completed"
        run.stages[0].output = "Saved research"
        run.stages[1].status = "active"
        run.stages[1].started_at = tasks.now()
        repository.save(run)
        tasks.recover_interrupted()
        recovered = repository.get(run.id)
        self.assertEqual([s.status for s in recovered.stages],
                         ["completed", "failed", "waiting", "waiting", "waiting"])
        self.assertEqual(recovered.stages[0].output, "Saved research")
        self.assertIn("Server restarted", recovered.stages[1].error)

    async def test_websocket_envelope_contains_real_events(self):
        # Use the real manager and an actual local TestClient WebSocket.
        self.socket_patch.stop()
        try:
            with TestClient(app) as client:
                with client.websocket_connect("/ws/live") as websocket:
                    response = client.post("/api/v1/simulations", json={"directive": "Socket test"})
                    self.assertEqual(response.status_code, 201)
                    seen = []
                    while True:
                        event = websocket.receive_json()
                        self.assertIn("timestamp", event)
                        seen.append(event["event"])
                        if event["event"] == "simulation_completed":
                            self.assertEqual(event["data"]["simulationId"], response.json()["id"])
                            break
                    self.assertEqual(seen.count("agent_completed"), 5)
                    self.assertEqual(seen.count("message_sent"), 4)
                    self.assertEqual(seen.count("message_created"), 4)
                    self.assertIn("task_updated", seen)
        finally:
            self.socket_patch.start()
    async def test_single_websocket_has_one_stage_and_no_handoffs(self):
        self.socket_patch.stop()
        try:
            with TestClient(app) as client:
                with client.websocket_connect("/ws/live") as websocket:
                    response = client.post("/api/v1/simulations", json={
                        "directive": "Socket baseline", "executionMode": "single"})
                    self.assertEqual(response.status_code, 201)
                    seen = []
                    while True:
                        event = websocket.receive_json()
                        seen.append(event)
                        if event["event"] == "simulation_completed":
                            break
                    self.assertEqual(sum(e["event"] == "agent_completed" for e in seen), 1)
                    self.assertFalse(any(e["event"] in ("message_sent", "message_created") for e in seen))
                    stage = next(e for e in seen if e["event"] == "agent_completed")
                    self.assertEqual(stage["data"]["executionMode"], "single")
                    self.assertEqual(stage["data"]["agentId"], "direct")
                    self.assertTrue(any(e["event"] == "task_updated" and
                                        [s["agentId"] for s in e["data"]["stages"]] == ["direct"]
                                        for e in seen))
        finally:
            self.socket_patch.start()
    async def test_api_upload_export_and_camel_case(self):
        with TestClient(app) as client:
            upload = client.post("/api/v1/uploads?filename=reference.csv",
                content=b"name,value\na,42\n", headers={"Content-Type": "text/csv"})
            self.assertEqual(upload.status_code, 201, upload.text)
            self.assertEqual(upload.json()["rowCount"], 1)
            response = client.post("/api/v1/simulations", json={
                "directive": "Original goal", "uploadIds": [upload.json()["id"]]})
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()["status"], "queued")
            run_id = response.json()["id"]
            run = client.get("/api/v1/simulations/" + run_id).json()
            self.assertEqual(run["status"], "completed")
            self.assertEqual(run["output"], "report actual output")
            self.assertEqual(len(run["stages"]), 5)
            self.assertEqual(len(client.get("/api/v1/simulations/"+run_id+"/events").json()), 17)
            for fmt in ("txt", "json", "csv"):
                export = client.get(f"/api/v1/simulations/{run_id}/export?format={fmt}")
                self.assertEqual(export.status_code, 200)
                self.assertIn(run_id, export.headers["content-disposition"])
            metrics = client.get("/api/v1/simulations/metrics").json()
            self.assertEqual(metrics["summary"]["completedTasks"], 1)
            self.assertEqual(metrics["summary"]["totalAgentExecutions"], 5)
            self.assertEqual(metrics["summary"]["measuredExecutions"], 0)
            self.assertEqual(client.get("/api/v1/tasks/" + run_id).json()["executionMode"], "fixed")
            self.assertEqual(client.post("/api/v1/uploads?filename=bad.exe", content=b"x").status_code, 415)
            self.assertEqual(client.post("/api/v1/uploads?filename=bad.json", content=b"{").status_code, 422)
            self.assertEqual(client.post("/api/v1/uploads?filename=large.txt",
                                        content=b"x"*262145).status_code, 413)
    async def test_research_modes_capture_matched_input_provenance(self):
        payloads = (
            CreateTaskRequest(
                directive="Analyze tradeoffs",
                title="Single presentation title",
                execution_mode="single",
                task_type="analysis",
            ),
            CreateTaskRequest(
                directive="Analyze tradeoffs",
                title="Fixed presentation title",
                execution_mode="fixed",
                task_type="analysis",
            ),
            CreateTaskRequest(
                directive="Analyze tradeoffs",
                title="Adaptive presentation title",
                execution_mode="adaptive",
                task_type="analysis",
            ),
        )

        runs = [
            await tasks.create_task(payload, BackgroundTasks())
            for payload in payloads
        ]

        self.assertTrue(all(run.provenance is not None for run in runs))

        fingerprints = {
            run.provenance.input_fingerprint
            for run in runs
        }
        self.assertEqual(len(fingerprints), 1)

        self.assertEqual(
            [run.execution_mode.value for run in runs],
            ["single", "fixed", "adaptive"],
        )

        self.assertIsNone(runs[0].provenance.router_version)
        self.assertIsNone(runs[1].provenance.router_version)
        self.assertEqual(runs[2].provenance.router_version, "rules-v1")

        for run in runs:
            self.assertEqual(
                run.provenance.requested_task_type,
                "analysis",
            )
            self.assertEqual(
                run.provenance.configured_model,
                tasks.DEFAULT_MODEL,
            )
            self.assertEqual(
                run.provenance.max_output_tokens,
                tasks.DEFAULT_MAX_TOKENS,
            )


    async def test_adaptive_provenance_preserves_requested_task_type_before_inference(self):
        from app.api.routes.uploads import parse_upload

        upload = parse_upload(
            "table.csv",
            b"department,count\nEngineering,4",
        )
        repository.save_upload(upload)

        queued = await tasks.create_task(
            CreateTaskRequest(
                directive="Analyze supplied data",
                execution_mode="adaptive",
                upload_ids=[upload.id],
            ),
            BackgroundTasks(),
        )

        self.assertEqual(
            queued.task_type,
            "structured_data_analysis",
        )
        self.assertIsNone(
            queued.provenance.requested_task_type,
        )
        self.assertEqual(
            queued.provenance.router_version,
            "rules-v1",
        )


    async def test_legacy_specialist_utility_has_no_research_provenance(self):
        queued = await tasks.create_task(
            CreateTaskRequest(
                directive="Inspect this input",
                execution_mode="single_agent",
                assigned_agent_id="analysis",
            ),
            BackgroundTasks(),
        )

        self.assertIsNone(queued.provenance)


    async def test_provenance_survives_repository_reopen(self):
        queued = await tasks.create_task(
            CreateTaskRequest(
                directive="Analyze tradeoffs",
                execution_mode="single",
                task_type="analysis",
            ),
            BackgroundTasks(),
        )

        expected = queued.provenance

        reopened = Repository("sqlite:///" + self.path)
        reopened.initialize()
        restored = reopened.get(queued.id)

        self.assertEqual(restored.provenance, expected)


    async def test_historical_task_without_provenance_remains_valid(self):
        queued = await tasks.create_task(
            CreateTaskRequest(
                directive="Historical compatibility",
                execution_mode="single",
            ),
            BackgroundTasks(),
        )

        snapshot = queued.model_dump(mode="json")
        snapshot.pop("provenance")

        from app.models.schemas import Task

        restored = Task.model_validate(snapshot)

        self.assertIsNone(restored.provenance)

    async def test_metrics_marks_missing_token_usage_unavailable(self):
        from app.api.routes import simulations

        run = await self.run_task(mode="single")

        result = await simulations.metrics()
        history = next(item for item in result["history"] if item["id"] == run.id)

        self.assertEqual(history["startedStageCount"], 1)
        self.assertEqual(history["measuredStageCount"], 0)
        self.assertEqual(history["tokenCoverage"], "unavailable")
        self.assertIsNone(history["tokens"])


    async def test_metrics_preserves_real_zero_as_complete_measurement(self):
        from app.api.routes import simulations

        run = await self.run_task(mode="single")

        run.stages[0].input_tokens = 0
        run.stages[0].output_tokens = 0
        run.stages[0].total_tokens = 0
        repository.save(run)

        result = await simulations.metrics()
        history = next(item for item in result["history"] if item["id"] == run.id)

        self.assertEqual(history["startedStageCount"], 1)
        self.assertEqual(history["measuredStageCount"], 1)
        self.assertEqual(history["tokenCoverage"], "complete")
        self.assertEqual(history["tokens"], 0)


    async def test_metrics_does_not_publish_partial_token_total_as_complete(self):
        from app.api.routes import simulations

        run = await self.run_task(mode="fixed")

        run.stages[0].input_tokens = 3
        run.stages[0].output_tokens = 2
        run.stages[0].total_tokens = 5
        repository.save(run)

        result = await simulations.metrics()
        history = next(item for item in result["history"] if item["id"] == run.id)
        self.assertEqual(history["startedStageCount"], 5)
        self.assertEqual(history["measuredStageCount"], 1)
        self.assertEqual(history["tokenCoverage"], "partial")
        self.assertIsNone(history["tokens"])
if __name__ == "__main__":
    unittest.main()
