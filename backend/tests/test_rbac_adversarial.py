"""Phase 4.3.6 adversarial RBAC verification.

These tests exercise privilege-escalation and stale-access attempts through the
public API. They intentionally use direct requests rather than frontend
controls so the backend remains the authoritative security boundary.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import Task, TaskExecutionMode, TaskPriority, TaskStatus
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


def _task(task_id: str, workspace_id: str):
    stamp = _now()
    return Task(
        id=task_id,
        simulation_id=task_id,
        directive="RBAC adversarial run",
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


def _session_client(user_id: str):
    raw = create_opaque_token()
    repository.save_auth_session(
        {
            "id": f"SES-{user_id}",
            "user_id": user_id,
            "token_digest": token_digest(raw),
            "created_at": _now().isoformat(),
            "expires_at": session_expiry().isoformat(),
            "revoked_at": None,
        }
    )
    client = TestClient(app)
    client.cookies.set("app_session", raw)
    return client


def _setup():
    temp = tempfile.TemporaryDirectory()
    path = str(Path(temp.name) / "rbac-adversarial.db")
    old_path = repository.path
    old_engine = repository._engine
    old_engine_url = repository._engine_url

    repository.path = path
    repository._engine = None
    repository._engine_url = None
    repository.initialize()

    users = {
        user_id: _user(user_id)
        for user_id in (
            "USR-owner-a",
            "USR-admin-a",
            "USR-member-a",
            "USR-owner-b",
            "USR-outsider",
        )
    }
    for record in users.values():
        repository.save_user(record)
        repository.ensure_personal_workspace(record["id"])

    org_a, code_a = repository.create_organization(
        creator_user_id="USR-owner-a",
        name="IICT",
    )
    repository.join_organization(user_id="USR-admin-a", join_code=code_a)
    code_a = repository.manage_organization_invites(workspace_id=org_a["id"], user_id="USR-owner-a", action="generate")["joinCode"]
    repository.join_organization(user_id="USR-member-a", join_code=code_a)
    repository.change_organization_membership_role(
        workspace_id=org_a["id"],
        actor_user_id="USR-owner-a",
        target_user_id="USR-admin-a",
        new_role="admin",
    )

    org_b, _ = repository.create_organization(
        creator_user_id="USR-owner-b",
        name="External Org",
    )

    repository.save(_task("T-org-a", org_a["id"]))
    repository.save(_task("T-org-b", org_b["id"]))

    clients = {user_id: _session_client(user_id) for user_id in users}
    return temp, old_path, old_engine, old_engine_url, org_a, org_b, clients


def _teardown(temp, old_path, old_engine, old_engine_url, clients):
    for client in clients.values():
        client.close()
    if repository._engine is not None:
        repository._engine.dispose()
    repository.path = old_path
    repository._engine = old_engine
    repository._engine_url = old_engine_url
    temp.cleanup()


def test_member_cannot_self_promote_to_admin_even_with_direct_api_call():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, org_a, _, clients = case
    try:
        response = clients["USR-member-a"].patch(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members/USR-member-a/role",
            json={"membershipRole": "admin"},
        )
        assert response.status_code == 403
        membership = repository.get_organization_membership(org_a["id"], "USR-member-a")
        assert membership["membership_role"] == "member"
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)


def test_admin_cannot_escalate_self_or_another_member_to_privileged_roles():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, org_a, _, clients = case
    try:
        self_owner = clients["USR-admin-a"].patch(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members/USR-admin-a/role",
            json={"membershipRole": "owner"},
        )
        member_admin = clients["USR-admin-a"].patch(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members/USR-member-a/role",
            json={"membershipRole": "admin"},
        )

        assert self_owner.status_code == 403
        assert member_admin.status_code == 403
        assert repository.get_organization_membership(org_a["id"], "USR-admin-a")["membership_role"] == "admin"
        assert repository.get_organization_membership(org_a["id"], "USR-member-a")["membership_role"] == "member"
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)


def test_owner_of_one_organization_cannot_tamper_with_another_organization():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, _, org_b, clients = case
    try:
        response = clients["USR-owner-a"].patch(
            f"/api/v1/workspaces/organizations/{org_b['id']}/members/USR-owner-b/role",
            json={"membershipRole": "member"},
        )
        assert response.status_code == 404
        assert repository.get_organization_membership(org_b["id"], "USR-owner-b")["membership_role"] == "owner"
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)


def test_forged_workspace_header_cannot_read_other_organization_runs():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, _, org_b, clients = case
    try:
        response = clients["USR-member-a"].get(
            "/api/v1/tasks",
            headers={"X-Workspace-Id": org_b["id"]},
        )
        assert response.status_code == 404
        assert "T-org-b" not in response.text
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)


def test_demotion_takes_effect_immediately_for_management_permissions():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, org_a, _, clients = case
    try:
        before = clients["USR-admin-a"].get(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members"
        )
        assert before.status_code == 200

        demote = clients["USR-owner-a"].patch(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members/USR-admin-a/role",
            json={"membershipRole": "member"},
        )
        assert demote.status_code == 200

        after = clients["USR-admin-a"].get(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members"
        )
        assert after.status_code == 403
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)


def test_inactive_membership_revokes_workspace_access_even_with_live_session():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, org_a, _, clients = case
    try:
        membership = repository.get_organization_membership(org_a["id"], "USR-member-a")
        membership["active"] = False
        repository.save_organization_membership(membership)

        response = clients["USR-member-a"].get(
            "/api/v1/tasks",
            headers={"X-Workspace-Id": org_a["id"]},
        )
        assert response.status_code == 404
        assert "T-org-a" not in response.text
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)


def test_last_owner_cannot_remove_own_ownership_through_direct_api_call():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, org_a, _, clients = case
    try:
        response = clients["USR-owner-a"].patch(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members/USR-owner-a/role",
            json={"membershipRole": "member"},
        )
        assert response.status_code == 409
        assert repository.get_organization_membership(org_a["id"], "USR-owner-a")["membership_role"] == "owner"
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)


def test_personal_workspace_never_grants_organization_management_permissions():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, _, _, clients = case
    try:
        personal = repository.get_personal_workspace("USR-owner-a")
        response = clients["USR-owner-a"].get(
            f"/api/v1/workspaces/organizations/{personal['id']}/members"
        )
        assert response.status_code == 403
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)
