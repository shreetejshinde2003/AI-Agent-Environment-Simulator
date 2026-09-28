"""Isolated coordinator/API tests; no Groq requests or user database writes."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from app.api.routes import tasks
from app.main import app
from app.models.schemas import CreateTaskRequest, TaskExecutionMode
from app.storage.database import repository, Repository

class FakeAgent:
    def __init__(self, name, order, failure=None):
        self.name, self.order, self.failure = name, order, failure
        self.calls = []
    async def run(self, directive, context=None):
        self.order.append(self.name)
        self.calls.append((directive, dict(context or {})))
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
        self.agent_patch = patch.object(tasks, "_IMPLEMENTED_AGENTS", self.agents)
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
    async def test_direct_mode(self):
        run = await self.run_task("analysis", "single_agent")
        self.assertEqual(self.order, ["analysis"])
        self.assertEqual(run.output, "analysis actual output")
        self.assertEqual(run.messages, [])
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
            self.assertEqual(client.get("/api/v1/tasks/" + run_id).json()["executionMode"], "full_pipeline")
            self.assertEqual(client.post("/api/v1/uploads?filename=bad.exe", content=b"x").status_code, 415)
            self.assertEqual(client.post("/api/v1/uploads?filename=bad.json", content=b"{").status_code, 422)
            self.assertEqual(client.post("/api/v1/uploads?filename=large.txt",
                                        content=b"x"*262145).status_code, 413)

if __name__ == "__main__":
    unittest.main()
