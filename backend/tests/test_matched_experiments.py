"""Matched experiment API tests; no provider requests."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.api.routes import experiments, tasks
from app.main import app
from app.models.schemas import RoutePlan
from app.security.session import create_opaque_token, session_expiry, token_digest
from app.storage.database import repository


class MatchedExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "test.db")

        self.path_patch = patch.object(repository, "path", self.path)
        self.path_patch.start()

        repository.initialize()
        tasks._TASKS.clear()

        stamp = datetime.now(timezone.utc).isoformat()
        repository.save_user(
            {
                "id": "USR-experiment",
                "google_sub": "google-experiment",
                "email": "experiment@example.com",
                "display_name": "Experiment User",
                "profile_picture": None,
                "email_verified": True,
                "active": True,
                "created_at": stamp,
                "last_login_at": stamp,
            }
        )
        self.workspace = repository.ensure_personal_workspace("USR-experiment")
        token = create_opaque_token()
        repository.save_auth_session(
            {
                "id": "SES-experiment",
                "user_id": "USR-experiment",
                "token_digest": token_digest(token),
                "created_at": stamp,
                "expires_at": session_expiry().isoformat(),
                "revoked_at": None,
            }
        )

        async def persist_without_execution(
            task, background_tasks, *, user_id=None
        ):
            if user_id is not None and task.workspace_id is not None:
                repository.save_for_tenant(
                    task, workspace_id=task.workspace_id, user_id=user_id
                )
            else:
                repository.save(task)
            return task.model_copy(deep=True)

        self.enqueue_patch = patch.object(
            experiments,
            "enqueue_task",
            new=AsyncMock(side_effect=persist_without_execution),
        )
        self.enqueue = self.enqueue_patch.start()

        self.client = TestClient(app)
        self.client.cookies.set("app_session", token)

    def tearDown(self):
        self.client.close()
        tasks._TASKS.clear()
        self.enqueue_patch.stop()
        self.path_patch.stop()
        self.temp.cleanup()

    def test_matched_endpoint_creates_exact_three_linked_runs(self):
        response = self.client.post(
            "/api/v1/experiments/matched",
            json={
                "directive": (
                    "Summarize the main tradeoffs of using a multi-agent "
                    "workflow instead of a single-agent workflow."
                )
            },
        )

        self.assertEqual(response.status_code, 201)

        body = response.json()

        self.assertTrue(body["experimentId"].startswith("E-"))
        self.assertEqual(len(body["inputFingerprint"]), 64)

        self.assertEqual(
            [run["executionMode"] for run in body["runs"]],
            ["single", "fixed", "adaptive"],
        )

        self.assertEqual(len(body["runs"]), 3)

        task_ids = [run["taskId"] for run in body["runs"]]
        self.assertEqual(len(set(task_ids)), 3)

        persisted = [repository.get(task_id) for task_id in task_ids]

        self.assertTrue(all(task is not None for task in persisted))
        self.assertEqual(
            {task.experiment_id for task in persisted},
            {body["experimentId"]},
        )

        fingerprints = {
            task.provenance.input_fingerprint
            for task in persisted
        }

        self.assertEqual(fingerprints, {body["inputFingerprint"]})

        self.assertEqual(
            [task.execution_mode.value for task in persisted],
            ["single", "fixed", "adaptive"],
        )

        self.assertEqual(
            {task.workspace_id for task in persisted},
            {self.workspace["id"]},
        )

        self.assertEqual(
            [stage.agent_id for stage in persisted[0].stages],
            ["direct"],
        )

        self.assertEqual(
            [stage.agent_id for stage in persisted[1].stages],
            ["research", "data", "analysis", "summarizer", "report"],
        )

        self.assertEqual(
            persisted[2].provenance.router_version,
            "rules-v1",
        )

        self.assertIsNone(persisted[0].provenance.router_version)
        self.assertIsNone(persisted[1].provenance.router_version)

        self.assertEqual(self.enqueue.await_count, 3)

    def test_invalid_adaptive_preparation_enqueues_nothing(self):
        invalid_plan = RoutePlan(
            router_version="rules-v1",
            execution_mode="adaptive",
            task_type="mixed",
            selected_agent_ids=(),
            skipped_agent_ids=(
                "research",
                "data",
                "analysis",
                "summarizer",
                "report",
            ),
            required_capabilities=(),
            available_inputs=(),
            reasons=("Controlled invalid route for test.",),
            validation_status="invalid",
            validation_error="Controlled invalid route.",
        )

        with patch.object(tasks, "plan_route", return_value=invalid_plan):
            response = self.client.post(
                "/api/v1/experiments/matched",
                json={
                    "directive": (
                        "Summarize the main tradeoffs of using a multi-agent "
                        "workflow instead of a single-agent workflow."
                    )
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.enqueue.await_count, 0)
        self.assertEqual(repository.list(), [])

    def test_matched_endpoint_rejects_blank_directive(self):
        response = self.client.post(
            "/api/v1/experiments/matched",
            json={"directive": "   "},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.enqueue.await_count, 0)
        self.assertEqual(repository.list(), [])