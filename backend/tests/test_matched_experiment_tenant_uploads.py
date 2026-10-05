"""Matched experiments must prepare all runs inside the authenticated tenant."""

from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks

from app.api.routes import experiments as experiment_routes


@pytest.mark.asyncio
async def test_matched_experiment_propagates_workspace_and_user_to_all_prepare_calls(
    monkeypatch,
):
    prepared = []

    monkeypatch.setattr(
        experiment_routes,
        "require_request_permission",
        lambda request, workspace_id, permission: {"id": "WS-a"},
    )
    monkeypatch.setattr(
        experiment_routes,
        "request_user_id",
        lambda request: "USR-a",
    )

    def fake_prepare_task(payload, **kwargs):
        prepared.append(kwargs)
        return SimpleNamespace(
            id=f"T-{len(prepared)}",
            provenance=SimpleNamespace(input_fingerprint="a" * 64),
        )

    async def fake_enqueue_task(task, background_tasks, user_id=None):
        assert user_id == "USR-a"
        return task

    monkeypatch.setattr(experiment_routes, "prepare_task", fake_prepare_task)
    monkeypatch.setattr(experiment_routes, "enqueue_task", fake_enqueue_task)

    payload = SimpleNamespace(
        directive="Compare the same input",
        title="Matched",
        priority="medium",
        upload_ids=["U-tenant"],
        dataset_id=None,
        task_type=None,
    )

    result = await experiment_routes.create_matched_experiment(
        payload,
        BackgroundTasks(),
        SimpleNamespace(),
        x_workspace_id="WS-a",
    )

    assert result.input_fingerprint == "a" * 64
    assert len(prepared) == 3
    assert all(call["workspace_id"] == "WS-a" for call in prepared)
    assert all(call["user_id"] == "USR-a" for call in prepared)
