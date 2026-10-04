"""Phase 4.2.10 adversarial multi-user / multi-organization verification."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

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


def task(task_id: str, workspace_id: str):
    stamp = now()
    return Task(
        id=task_id,
        simulation_id=task_id,
        directive=task_id,
        assigned_agent_id="direct",
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.MEDIUM,
        execution_mode=TaskExecutionMode.SINGLE,
        started_at=stamp,
        created_at=stamp,
        completed_at=stamp,
        duration_seconds=1,
        progress_percent=100,
        output=f"output-{task_id}",
        workspace_id=workspace_id,
    )


def authenticated_client(user_id: str):
    client = TestClient(app)
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
    client.cookies.set("app_session", token)
    return client


def setup_world():
    temp = tempfile.TemporaryDirectory()
    path = str(Path(temp.name) / "multi-tenant.db")
    old = (repository.path, repository._engine, repository._engine_url)
    repository.path = path
    repository._engine = None
    repository._engine_url = None
    repository.initialize()

    alice = user_record("USR-alice")
    bob = user_record("USR-bob")
    eve = user_record("USR-eve")
    for user in (alice, bob, eve):
        repository.save_user(user)
        repository.ensure_personal_workspace(user["id"])

    iict, _ = repository.create_organization(
        creator_user_id=alice["id"], name="IICT"
    )
    other, _ = repository.create_organization(
        creator_user_id=eve["id"], name="Other Organization"
    )
    repository.save_organization_membership(
        {
            "workspace_id": iict["id"],
            "user_id": bob["id"],
            "membership_role": "member",
            "active": True,
            "joined_at": now().isoformat(),
            "added_by_user_id": alice["id"],
        }
    )
    return temp, old, alice, bob, eve, iict, other


def cleanup(temp, old, *clients):
    for client in clients:
        client.close()
    if repository._engine is not None:
        repository._engine.dispose()
    repository.path, repository._engine, repository._engine_url = old
    temp.cleanup()


def test_personal_workspaces_are_private_between_two_authenticated_users():
    temp, old, alice, bob, _, _, _ = setup_world()
    alice_ws = repository.get_personal_workspace(alice["id"])
    repository.save(task("T-alice-private", alice_ws["id"]))
    a = authenticated_client(alice["id"])
    b = authenticated_client(bob["id"])
    try:
        assert {r["id"] for r in a.get("/api/v1/tasks").json()} == {"T-alice-private"}
        assert b.get(
            "/api/v1/tasks/T-alice-private",
            headers={"X-Workspace-Id": alice_ws["id"]},
        ).status_code == 404
    finally:
        cleanup(temp, old, a, b)


def test_two_members_share_same_organization_runs_but_outsider_cannot_probe_them():
    temp, old, alice, bob, eve, iict, _ = setup_world()
    repository.save(task("T-iict-shared", iict["id"]))
    a = authenticated_client(alice["id"])
    b = authenticated_client(bob["id"])
    e = authenticated_client(eve["id"])
    header = {"X-Workspace-Id": iict["id"]}
    try:
        assert {r["id"] for r in a.get("/api/v1/tasks", headers=header).json()} == {"T-iict-shared"}
        assert {r["id"] for r in b.get("/api/v1/tasks", headers=header).json()} == {"T-iict-shared"}
        assert e.get("/api/v1/tasks", headers=header).status_code == 404
        assert e.get("/api/v1/tasks/T-iict-shared", headers=header).status_code == 404
    finally:
        cleanup(temp, old, a, b, e)


def test_inactive_membership_immediately_removes_organization_access():
    temp, old, alice, bob, _, iict, _ = setup_world()
    membership = repository.get_organization_membership(iict["id"], bob["id"])
    membership["active"] = False
    repository.save_organization_membership(membership)
    b = authenticated_client(bob["id"])
    try:
        response = b.get(
            "/api/v1/tasks",
            headers={"X-Workspace-Id": iict["id"]},
        )
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "workspace_unavailable"
    finally:
        cleanup(temp, old, b)


def test_user_cannot_swap_to_unrelated_org_for_metrics_or_exports():
    temp, old, alice, _, _, _, other = setup_world()
    repository.save(task("T-other", other["id"]))
    a = authenticated_client(alice["id"])
    header = {"X-Workspace-Id": other["id"]}
    try:
        assert a.get("/api/v1/simulations/metrics", headers=header).status_code == 404
        assert a.get("/api/v1/simulations/T-other/export", headers=header).status_code == 404
    finally:
        cleanup(temp, old, a)
