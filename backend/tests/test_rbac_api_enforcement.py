"""Phase 4.3.4 integration checks for centralized simulation RBAC gates."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.models.schemas import Task, TaskExecutionMode, TaskPriority, TaskStatus
from app.security.rbac import Permission, ROLE_PERMISSIONS, WorkspaceRole
from app.security.session import create_opaque_token, session_expiry, token_digest
from app.storage.database import repository


def _now():
    return datetime.now(timezone.utc)


def _user(user_id: str):
    stamp = _now().isoformat()
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


def _completed_task(task_id: str, workspace_id: str):
    stamp = _now()
    return Task(
        id=task_id,
        simulation_id=task_id,
        directive="RBAC test run",
        assigned_agent_id="direct",
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.MEDIUM,
        execution_mode=TaskExecutionMode.SINGLE,
        started_at=stamp,
        created_at=stamp,
        completed_at=stamp,
        duration_seconds=1,
        progress_percent=100,
        output="done",
        workspace_id=workspace_id,
    )


@pytest.fixture
def member_context():
    temp = tempfile.TemporaryDirectory()
    path = str(Path(temp.name) / "rbac-api.db")
    old_path = repository.path
    old_engine = repository._engine
    old_engine_url = repository._engine_url

    repository.path = path
    repository._engine = None
    repository._engine_url = None
    repository.initialize()

    owner = _user("USR-owner")
    member = _user("USR-member")
    repository.save_user(owner)
    repository.save_user(member)
    workspace, join_code = repository.create_organization(
        creator_user_id=owner["id"],
        name="IICT",
    )
    repository.join_organization(
        user_id=member["id"],
        join_code=join_code,
    )
    repository.save(_completed_task("T-rbac", workspace["id"]))

    token = create_opaque_token()
    repository.save_auth_session(
        {
            "id": "SES-member",
            "user_id": member["id"],
            "token_digest": token_digest(token),
            "created_at": _now().isoformat(),
            "expires_at": session_expiry().isoformat(),
            "revoked_at": None,
        }
    )

    client = TestClient(app)
    client.cookies.set("app_session", token)
    yield client, workspace

    client.close()
    if repository._engine is not None:
        repository._engine.dispose()
    repository.path = old_path
    repository._engine = old_engine
    repository._engine_url = old_engine_url
    temp.cleanup()


def _without(permission: Permission):
    return frozenset(
        item
        for item in ROLE_PERMISSIONS[WorkspaceRole.MEMBER]
        if item is not permission
    )


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/tasks",
        "/api/v1/tasks/T-rbac",
        "/api/v1/simulations",
        "/api/v1/simulations/metrics",
        "/api/v1/simulations/T-rbac",
        "/api/v1/simulations/T-rbac/events",
        "/api/v1/simulation/stats",
        "/api/v1/simulation/activity?simulation_id=T-rbac",
        "/api/v1/messages?simulation_id=T-rbac",
    ],
)
def test_simulation_read_surfaces_require_view_permission(
    member_context,
    monkeypatch,
    path,
):
    client, workspace = member_context
    monkeypatch.setitem(
        ROLE_PERMISSIONS,
        WorkspaceRole.MEMBER,
        _without(Permission.SIMULATION_VIEW),
    )

    response = client.get(
        path,
        headers={"X-Workspace-Id": workspace["id"]},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "permission_denied"


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/api/v1/tasks",
            {"directive": "Denied task", "executionMode": "single"},
        ),
        (
            "/api/v1/simulations",
            {"directive": "Denied simulation", "executionMode": "single"},
        ),
        (
            "/api/v1/experiments/matched",
            {"directive": "Denied matched experiment"},
        ),
    ],
)
def test_simulation_creation_surfaces_require_create_permission(
    member_context,
    monkeypatch,
    path,
    payload,
):
    client, workspace = member_context
    monkeypatch.setitem(
        ROLE_PERMISSIONS,
        WorkspaceRole.MEMBER,
        _without(Permission.SIMULATION_CREATE),
    )

    response = client.post(
        path,
        headers={"X-Workspace-Id": workspace["id"]},
        json=payload,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "permission_denied"


def test_quality_evaluation_requires_evaluate_permission(member_context, monkeypatch):
    client, workspace = member_context
    monkeypatch.setitem(
        ROLE_PERMISSIONS,
        WorkspaceRole.MEMBER,
        _without(Permission.SIMULATION_EVALUATE),
    )

    response = client.post(
        "/api/v1/tasks/T-rbac/evaluate",
        headers={"X-Workspace-Id": workspace["id"]},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "permission_denied"


def test_export_requires_export_permission(member_context, monkeypatch):
    client, workspace = member_context
    monkeypatch.setitem(
        ROLE_PERMISSIONS,
        WorkspaceRole.MEMBER,
        _without(Permission.SIMULATION_EXPORT),
    )

    response = client.get(
        "/api/v1/simulations/T-rbac/export",
        headers={"X-Workspace-Id": workspace["id"]},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "permission_denied"


def test_matched_experiment_runs_are_owned_by_selected_workspace(member_context):
    client, workspace = member_context

    with patch("app.api.routes.tasks._run_task", new=AsyncMock()):
        response = client.post(
            "/api/v1/experiments/matched",
            headers={"X-Workspace-Id": workspace["id"]},
            json={"directive": "Compare strategies"},
        )

    assert response.status_code == 201
    run_ids = [run["taskId"] for run in response.json()["runs"]]
    assert len(run_ids) == 3
    assert all(
        repository.get(task_id).workspace_id == workspace["id"]
        for task_id in run_ids
    )


def test_websocket_requires_workspace_view_permission(member_context, monkeypatch):
    client, workspace = member_context
    monkeypatch.setitem(
        ROLE_PERMISSIONS,
        WorkspaceRole.MEMBER,
        _without(Permission.WORKSPACE_VIEW),
    )

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            f"/ws/live?workspaceId={workspace['id']}"
        ):
            pass

    assert exc.value.code == 4404
