"""Phase 4.5.4B trusted tenant identity wiring for run execution."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks

from app.api.routes import messages, simulation, tasks
from app.models.schemas import (
    MessageKind,
    Task,
    TaskExecutionMode,
    TaskPriority,
    TaskStatus,
)


def make_task(task_id: str = "T-wired") -> Task:
    now = datetime.now(timezone.utc)
    return Task(
        id=task_id,
        simulation_id=task_id,
        directive="tenant wiring test",
        assigned_agent_id="direct",
        execution_mode=TaskExecutionMode.SINGLE,
        status=TaskStatus.QUEUED,
        priority=TaskPriority.MEDIUM,
        duration_seconds=0,
        progress_percent=0,
        started_at=now,
        created_at=now,
        workspace_id="WS-a",
    )


def test_get_record_prefers_tenant_aware_repository(monkeypatch):
    task = make_task()
    called = {}

    def get_for_tenant(task_id, *, workspace_id, user_id):
        called.update(
            task_id=task_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        return task

    monkeypatch.setattr(tasks.repository, "get_for_tenant", get_for_tenant)
    monkeypatch.setattr(
        tasks.repository,
        "get_for_workspace",
        lambda *_args, **_kwargs: pytest.fail("legacy workspace read used"),
    )

    assert tasks.get_record("T-wired", "WS-a", "USR-a") is task
    assert called == {
        "task_id": "T-wired",
        "workspace_id": "WS-a",
        "user_id": "USR-a",
    }


@pytest.mark.asyncio
async def test_record_activity_persists_with_tenant_context(monkeypatch):
    task = make_task()
    saved = []

    monkeypatch.setattr(
        simulation.repository,
        "save_for_tenant",
        lambda item, *, workspace_id, user_id: saved.append(
            (item.id, workspace_id, user_id)
        ),
    )
    monkeypatch.setattr(
        simulation.repository,
        "save",
        lambda *_args, **_kwargs: pytest.fail("legacy save used"),
    )
    monkeypatch.setattr(simulation.manager, "broadcast", AsyncMock())

    await simulation.record_activity(
        "direct", "started", task=task, user_id="USR-a"
    )

    assert saved == [("T-wired", "WS-a", "USR-a")]


@pytest.mark.asyncio
async def test_record_message_persists_with_tenant_context(monkeypatch):
    task = make_task()
    saved = []

    monkeypatch.setattr(
        messages.repository,
        "save_for_tenant",
        lambda item, *, workspace_id, user_id: saved.append(
            (item.id, workspace_id, user_id)
        ),
    )
    monkeypatch.setattr(
        messages.repository,
        "save",
        lambda *_args, **_kwargs: pytest.fail("legacy save used"),
    )
    monkeypatch.setattr(messages.manager, "broadcast", AsyncMock())

    await messages.record_message(
        "research",
        "analysis",
        MessageKind.RESPONSE,
        "handoff",
        task=task,
        output_key="research_findings",
        user_id="USR-a",
    )

    assert saved == [("T-wired", "WS-a", "USR-a")]


@pytest.mark.asyncio
async def test_enqueue_carries_tenant_identity_into_background_task(monkeypatch):
    task = make_task()
    background = BackgroundTasks()
    saves = []

    monkeypatch.setattr(tasks, "emit", AsyncMock())
    monkeypatch.setattr(tasks.manager, "broadcast", AsyncMock())
    monkeypatch.setattr(tasks, "register_task_created", AsyncMock())
    monkeypatch.setattr(tasks, "record_activity", AsyncMock())
    monkeypatch.setattr(
        tasks.repository,
        "save_for_tenant",
        lambda item, *, workspace_id, user_id: saves.append(
            (item.id, workspace_id, user_id)
        ),
    )
    monkeypatch.setattr(
        tasks.repository,
        "save",
        lambda *_args, **_kwargs: pytest.fail("legacy save used"),
    )

    await tasks.enqueue_task(task, background, user_id="USR-a")

    assert saves == [("T-wired", "WS-a", "USR-a")]
    assert len(background.tasks) == 1
    queued = background.tasks[0]
    assert queued.func is tasks._run_task
    assert queued.args == ("T-wired", "WS-a", "USR-a")
