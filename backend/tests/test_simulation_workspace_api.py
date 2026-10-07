"""Phase 4.2.9B workspace-scoped simulation API tests."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import Task, TaskExecutionMode, TaskPriority, TaskStatus
from app.security.session import create_opaque_token, session_expiry, token_digest
from app.storage.database import repository


def now():
    return datetime.now(timezone.utc)


def user_record(user_id: str):
    stamp = now().isoformat()
    return {
        "id": user_id,
        "google_sub": f"google-{user_id}",
        "email": f"{user_id.lower()}@example.com",
        "display_name": user_id,
        "profile_picture": None,
        "email_verified": True,
        "active": True,
        "created_at": stamp,
        "last_login_at": stamp,
    }


def completed_task(task_id: str, workspace_id: str, directive: str):
    stamp = now()
    return Task(
        id=task_id,
        simulation_id=task_id,
        directive=directive,
        assigned_agent_id="direct",
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.MEDIUM,
        execution_mode=TaskExecutionMode.SINGLE,
        started_at=stamp,
        created_at=stamp,
        completed_at=stamp,
        duration_seconds=1,
        progress_percent=100,
        output=f"Output for {directive}",
        workspace_id=workspace_id,
    )


def authenticated_context(user_id: str = "USR-current"):
    temp = tempfile.TemporaryDirectory()
    path = str(Path(temp.name) / "workspace-api.db")

    old_path = repository.path
    old_engine = repository._engine
    old_engine_url = repository._engine_url

    repository.path = path
    repository._engine = None
    repository._engine_url = None
    repository.initialize()

    user = user_record(user_id)
    repository.save_user(user)
    personal = repository.ensure_personal_workspace(user_id)
    organization, _ = repository.create_organization(
        creator_user_id=user_id,
        name="IICT",
    )

    token = create_opaque_token()
    repository.save_auth_session(
        {
            "id": f"SES-{user_id}",
            "user_id": user_id,
            "token_digest": token_digest(token),
            "created_at": now().isoformat(),
            "expires_at": session_expiry().isoformat(),
            "revoked_at": None,
        }
    )

    client = TestClient(app)
    client.cookies.set("app_session", token)
    return client, user, personal, organization, temp, old_path, old_engine, old_engine_url


def cleanup(ctx):
    client, _, _, _, temp, old_path, old_engine, old_engine_url = ctx
    client.close()
    if repository._engine is not None:
        repository._engine.dispose()
    repository.path = old_path
    repository._engine = old_engine
    repository._engine_url = old_engine_url
    temp.cleanup()


def test_simulation_routes_require_authentication(isolated_startup_repository):
    with TestClient(app) as client:
        assert client.get("/api/v1/simulations").status_code == 401
        assert client.get("/api/v1/tasks").status_code == 401
        assert client.get("/api/v1/simulations/metrics").status_code == 401


def test_lists_are_scoped_to_selected_workspace_and_default_to_personal():
    ctx = authenticated_context()
    client, _, personal, organization, *_ = ctx
    try:
        repository.save(completed_task("T-personal", personal["id"], "Personal run"))
        repository.save(completed_task("T-iict", organization["id"], "IICT run"))

        default_ids = {item["id"] for item in client.get("/api/v1/simulations").json()}
        personal_ids = {
            item["id"]
            for item in client.get(
                "/api/v1/tasks", headers={"X-Workspace-Id": personal["id"]}
            ).json()
        }
        org_ids = {
            item["id"]
            for item in client.get(
                "/api/v1/simulations",
                headers={"X-Workspace-Id": organization["id"]},
            ).json()
        }

        assert default_ids == {"T-personal"}
        assert personal_ids == {"T-personal"}
        assert org_ids == {"T-iict"}
    finally:
        cleanup(ctx)


def test_cross_workspace_run_detail_events_and_export_are_hidden():
    ctx = authenticated_context()
    client, _, personal, organization, *_ = ctx
    try:
        repository.save(completed_task("T-secret", organization["id"], "IICT secret"))
        personal_header = {"X-Workspace-Id": personal["id"]}

        assert client.get("/api/v1/tasks/T-secret", headers=personal_header).status_code == 404
        assert client.get("/api/v1/simulations/T-secret", headers=personal_header).status_code == 404
        assert client.get("/api/v1/simulations/T-secret/events", headers=personal_header).status_code == 404
        assert client.get("/api/v1/simulations/T-secret/export", headers=personal_header).status_code == 404
    finally:
        cleanup(ctx)


def test_metrics_history_is_scoped_to_selected_workspace():
    ctx = authenticated_context()
    client, _, personal, organization, *_ = ctx
    try:
        repository.save(completed_task("T-personal", personal["id"], "Personal run"))
        repository.save(completed_task("T-iict", organization["id"], "IICT run"))

        personal = client.get(
            "/api/v1/simulations/metrics",
            headers={"X-Workspace-Id": personal["id"]},
        )
        org = client.get(
            "/api/v1/simulations/metrics",
            headers={"X-Workspace-Id": organization["id"]},
        )

        assert personal.status_code == 200
        assert org.status_code == 200
        assert {item["id"] for item in personal.json()["history"]} == {"T-personal"}
        assert {item["id"] for item in org.json()["history"]} == {"T-iict"}
    finally:
        cleanup(ctx)


def test_unrelated_workspace_is_404_and_created_task_uses_selected_workspace():
    ctx = authenticated_context()
    client, _, _, organization, *_ = ctx
    try:
        outsider = user_record("USR-outsider")
        repository.save_user(outsider)
        outsider_org, _ = repository.create_organization(
            creator_user_id=outsider["id"],
            name="Other Org",
        )

        unavailable = client.get(
            "/api/v1/simulations",
            headers={"X-Workspace-Id": outsider_org["id"]},
        )
        assert unavailable.status_code == 404
        assert unavailable.json()["detail"]["code"] == "workspace_unavailable"

        with patch("app.api.routes.tasks._run_task", new=AsyncMock()):
            created = client.post(
                "/api/v1/tasks",
                headers={"X-Workspace-Id": organization["id"]},
                json={"directive": "Workspace-owned run", "executionMode": "single"},
            )

        assert created.status_code == 201
        task_id = created.json()["id"]
        assert repository.get(task_id).workspace_id == organization["id"]
        assert repository.get_for_workspace(task_id, organization["id"]) is not None
    finally:
        cleanup(ctx)
