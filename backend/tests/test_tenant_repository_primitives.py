"""Tenant-aware simulation repository primitives for Phase 4.5.4A."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models.schemas import Task, TaskExecutionMode, TaskPriority, TaskStatus
from app.security.tenant_db_context import TenantContextError
from app.storage.database import repository


def make_task(task_id: str, workspace_id: str) -> Task:
    now = datetime.now(timezone.utc)
    return Task(
        id=task_id,
        simulation_id=task_id,
        directive="tenant isolation test",
        assigned_agent_id="direct",
        execution_mode=TaskExecutionMode.SINGLE,
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.MEDIUM,
        duration_seconds=0,
        progress_percent=100,
        started_at=now,
        created_at=now,
        completed_at=now,
        workspace_id=workspace_id,
    )


def make_user(user_id: str):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": user_id,
        "google_sub": f"google-{user_id}",
        "email": f"{user_id.lower()}@example.com",
        "display_name": user_id,
        "profile_picture": None,
        "email_verified": True,
        "active": True,
        "created_at": now,
        "last_login_at": now,
    }


def setup_repo():
    temp = tempfile.TemporaryDirectory()
    old_path = repository.path
    old_engine = repository._engine
    old_engine_url = repository._engine_url
    repository.path = str(Path(temp.name) / "tenant-primitives.db")
    repository._engine = None
    repository._engine_url = None
    repository.initialize()
    return temp, old_path, old_engine, old_engine_url


def teardown_repo(temp, old_path, old_engine, old_engine_url):
    if repository._engine is not None:
        repository._engine.dispose()
    repository.path = old_path
    repository._engine = old_engine
    repository._engine_url = old_engine_url
    temp.cleanup()


def test_tenant_save_get_and_list_are_workspace_scoped():
    temp, old_path, old_engine, old_engine_url = setup_repo()
    try:
        repository.save_user(make_user("USR-a"))
        repository.save_user(make_user("USR-b"))
        ws_a = repository.ensure_personal_workspace("USR-a")["id"]
        ws_b = repository.ensure_personal_workspace("USR-b")["id"]

        repository.save_for_tenant(
            make_task("T-a", ws_a), workspace_id=ws_a, user_id="USR-a"
        )
        repository.save_for_tenant(
            make_task("T-b", ws_b), workspace_id=ws_b, user_id="USR-b"
        )

        assert repository.get_for_tenant(
            "T-a", workspace_id=ws_a, user_id="USR-a"
        ).id == "T-a"
        assert repository.get_for_tenant(
            "T-b", workspace_id=ws_a, user_id="USR-a"
        ) is None
        assert [task.id for task in repository.list_for_tenant(
            workspace_id=ws_a, user_id="USR-a"
        )] == ["T-a"]
    finally:
        teardown_repo(temp, old_path, old_engine, old_engine_url)


def test_tenant_save_rejects_workspace_mismatch_before_persisting():
    temp, old_path, old_engine, old_engine_url = setup_repo()
    try:
        repository.save_user(make_user("USR-a"))
        ws_a = repository.ensure_personal_workspace("USR-a")["id"]
        with pytest.raises(ValueError, match="workspace does not match"):
            repository.save_for_tenant(
                make_task("T-wrong", ws_a),
                workspace_id="WS-other",
                user_id="USR-a",
            )
        assert repository.get("T-wrong") is None
    finally:
        teardown_repo(temp, old_path, old_engine, old_engine_url)


def test_tenant_repository_rejects_invalid_user_context():
    temp, old_path, old_engine, old_engine_url = setup_repo()
    try:
        with pytest.raises(TenantContextError):
            repository.list_for_tenant(workspace_id="W-a", user_id="")
    finally:
        teardown_repo(temp, old_path, old_engine, old_engine_url)


def test_tenant_repository_rejects_invalid_workspace_context():
    temp, old_path, old_engine, old_engine_url = setup_repo()
    try:
        with pytest.raises(TenantContextError):
            repository.get_for_tenant("T-a", workspace_id=" W-a", user_id="USR-a")
    finally:
        teardown_repo(temp, old_path, old_engine, old_engine_url)
