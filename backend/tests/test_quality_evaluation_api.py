"""Explicit quality-evaluation API tests; no real Groq requests."""

import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.api.routes import tasks
from app.experiments.evaluation import build_run_evaluation
from app.main import app
from app.models.schemas import (
    QualityCriterion,
    QualityJudgment,
    StageExecution,
    Task,
    TaskExecutionMode,
    TaskPriority,
    TaskStatus,
)
from app.storage.database import repository


def quality_judgment(output: str) -> QualityJudgment:
    return QualityJudgment(
        evaluator_provider="groq",
        evaluator_model="judge-test-model",
        treatment_blinded=True,
        output_sha256=hashlib.sha256(
            output.encode("utf-8")
        ).hexdigest(),
        criteria=(
            QualityCriterion(
                name="task_fulfillment",
                applicable=True,
                score=4,
                rationale="Addresses the requested task.",
            ),
            QualityCriterion(
                name="completeness",
                applicable=True,
                score=4,
                rationale="Covers the important requested content.",
            ),
            QualityCriterion(
                name="coherence",
                applicable=True,
                score=5,
                rationale="Clear and internally consistent.",
            ),
            QualityCriterion(
                name="grounding",
                applicable=False,
                score=None,
                rationale="No reference material was supplied.",
            ),
        ),
    )


class QualityEvaluationApiTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

        self.path = str(
            Path(self.temp.name) / "quality-evaluation.db"
        )

        self.path_patch = patch.object(
            repository,
            "path",
            self.path,
        )

        self.path_patch.start()
        repository.initialize()

    def tearDown(self):
        tasks._TASKS.clear()
        self.path_patch.stop()
        self.temp.cleanup()

    def make_task(
        self,
        *,
        mode=TaskExecutionMode.SINGLE,
        status=TaskStatus.COMPLETED,
        output="Candidate answer.",
    ):
        timestamp = datetime.now(timezone.utc)

        assigned_agent = (
            "analysis"
            if mode == TaskExecutionMode.SINGLE_AGENT
            else "direct"
        )

        stage = StageExecution(
            agent_id=assigned_agent,
            output_key=(
                "output"
                if mode == TaskExecutionMode.SINGLE_AGENT
                else "final_answer"
            ),
            status=(
                "completed"
                if status == TaskStatus.COMPLETED
                else "failed"
            ),
            started_at=timestamp,
            completed_at=timestamp,
            total_tokens=100,
        )

        task = Task(
            id="T-quality-api",
            simulation_id="T-quality-api",
            directive="Evaluate the candidate answer.",
            assigned_agent_id=assigned_agent,
            status=status,
            priority=TaskPriority.MEDIUM,
            execution_mode=mode,
            started_at=timestamp,
            created_at=timestamp,
            execution_started_at=timestamp,
            completed_at=timestamp,
            duration_seconds=1,
            elapsed_seconds=1.25,
            progress_percent=(
                100
                if status == TaskStatus.COMPLETED
                else 0
            ),
            stages=[stage],
            output=output,
        )

        if mode in (
            TaskExecutionMode.SINGLE,
            TaskExecutionMode.FIXED,
            TaskExecutionMode.ADAPTIVE,
        ):
            task.evaluation = build_run_evaluation(task)

        repository.save(task)

        return task

    def test_explicit_evaluation_persists_quality(self):
        task = self.make_task()
        judgment = quality_judgment(task.output)

        with patch.object(
            tasks,
            "evaluate_quality_judgment",
            new_callable=AsyncMock,
            return_value=judgment,
        ) as judge:
            with TestClient(app) as client:
                response = client.post(
                    f"/api/v1/tasks/{task.id}/evaluate"
                )

        self.assertEqual(
            response.status_code,
            200,
            response.text,
        )

        judge.assert_awaited_once()

        body = response.json()

        self.assertEqual(
            body["taskId"],
            task.id,
        )

        self.assertEqual(
            body["quality"]["evaluatorModel"],
            "judge-test-model",
        )

        self.assertTrue(
            body["quality"]["treatmentBlinded"],
        )

        restored = repository.get(task.id)

        self.assertIsNotNone(
            restored.evaluation,
        )

        self.assertIsNotNone(
            restored.evaluation.quality,
        )

        self.assertEqual(
            restored.evaluation.quality.evaluator_model,
            "judge-test-model",
        )

        self.assertEqual(
            restored.evaluation.objective,
            task.evaluation.objective,
        )

    def test_explicit_evaluation_is_idempotent(self):
        task = self.make_task()
        judgment = quality_judgment(task.output)

        with patch.object(
            tasks,
            "evaluate_quality_judgment",
            new_callable=AsyncMock,
            return_value=judgment,
        ) as judge:
            with TestClient(app) as client:
                first = client.post(
                    f"/api/v1/tasks/{task.id}/evaluate"
                )

                second = client.post(
                    f"/api/v1/tasks/{task.id}/evaluate"
                )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        self.assertEqual(
            judge.await_count,
            1,
        )

        self.assertEqual(
            first.json(),
            second.json(),
        )

    def test_failed_run_cannot_receive_quality_judgment(self):
        task = self.make_task(
            status=TaskStatus.FAILED,
            output=None,
        )

        with patch.object(
            tasks,
            "evaluate_quality_judgment",
            new_callable=AsyncMock,
        ) as judge:
            with TestClient(app) as client:
                response = client.post(
                    f"/api/v1/tasks/{task.id}/evaluate"
                )

        self.assertEqual(
            response.status_code,
            409,
        )

        self.assertEqual(
            response.json()["detail"]["code"],
            "task_not_completed",
        )

        judge.assert_not_awaited()

    def test_legacy_specialist_cannot_receive_research_quality_judgment(self):
        task = self.make_task(
            mode=TaskExecutionMode.SINGLE_AGENT,
        )

        with patch.object(
            tasks,
            "evaluate_quality_judgment",
            new_callable=AsyncMock,
        ) as judge:
            with TestClient(app) as client:
                response = client.post(
                    f"/api/v1/tasks/{task.id}/evaluate"
                )

        self.assertEqual(
            response.status_code,
            422,
        )

        self.assertEqual(
            response.json()["detail"]["code"],
            "evaluation_not_supported",
        )

        judge.assert_not_awaited()

    def test_invalid_judge_response_does_not_persist_quality(self):
        task = self.make_task()

        with patch.object(
            tasks,
            "evaluate_quality_judgment",
            new_callable=AsyncMock,
            side_effect=ValueError(
                "Quality evaluator returned invalid JSON."
            ),
        ):
            with TestClient(app) as client:
                response = client.post(
                    f"/api/v1/tasks/{task.id}/evaluate"
                )

        self.assertEqual(
            response.status_code,
            502,
        )

        self.assertEqual(
            response.json()["detail"]["code"],
            "invalid_evaluator_response",
        )

        restored = repository.get(task.id)

        self.assertIsNone(
            restored.evaluation.quality,
        )

    def test_provider_failure_does_not_persist_quality(self):
        task = self.make_task()

        with patch.object(
            tasks,
            "evaluate_quality_judgment",
            new_callable=AsyncMock,
            side_effect=RuntimeError(
                "controlled provider failure"
            ),
        ):
            with TestClient(app) as client:
                response = client.post(
                    f"/api/v1/tasks/{task.id}/evaluate"
                )

        self.assertEqual(
            response.status_code,
            502,
        )

        self.assertEqual(
            response.json()["detail"]["code"],
            "evaluation_provider_error",
        )

        restored = repository.get(task.id)

        self.assertIsNone(
            restored.evaluation.quality,
        )


if __name__ == "__main__":
    unittest.main()
