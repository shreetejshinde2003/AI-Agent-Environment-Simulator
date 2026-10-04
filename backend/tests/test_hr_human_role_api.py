"""Phase 4.4.2 HR human-role assignment API tests."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.security.session import create_opaque_token, session_expiry, token_digest
from app.storage.database import repository


def user(user_id: str, name: str, email: str):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": user_id,
        "google_sub": f"google-{user_id}",
        "email": email,
        "display_name": name,
        "profile_picture": None,
        "email_verified": True,
        "active": True,
        "created_at": now,
        "last_login_at": now,
    }


def setup_case():
    temp = tempfile.TemporaryDirectory()
    path = str(Path(temp.name) / "hr-role-api.db")
    old_path = repository.path
    old_engine = repository._engine
    old_engine_url = repository._engine_url

    repository.path = path
    repository._engine = None
    repository._engine_url = None
    repository.initialize()

    owner = user("USR-owner", "Owner", "owner@example.com")
    admin = user("USR-admin", "Admin", "admin@example.com")
    member = user("USR-member", "Member", "member@example.com")
    outsider = user("USR-outsider", "Outsider", "outsider@example.com")
    for record in (owner, admin, member, outsider):
        repository.save_user(record)
        repository.ensure_personal_workspace(record["id"])

    workspace, join_code = repository.create_organization(
        creator_user_id=owner["id"],
        name="IICT",
    )
    repository.join_organization(user_id=admin["id"], join_code=join_code)
    repository.join_organization(user_id=member["id"], join_code=join_code)
    repository.change_organization_membership_role(
        workspace_id=workspace["id"],
        actor_user_id=owner["id"],
        target_user_id=admin["id"],
        new_role="admin",
    )

    clients = {}
    for record in (owner, admin, member, outsider):
        raw = create_opaque_token()
        repository.save_auth_session(
            {
                "id": f"SES-{record['id']}",
                "user_id": record["id"],
                "token_digest": token_digest(raw),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": session_expiry().isoformat(),
                "revoked_at": None,
            }
        )
        client = TestClient(app)
        client.cookies.set("app_session", raw)
        clients[record["id"]] = client

    return temp, old_path, old_engine, old_engine_url, workspace, clients


def teardown_case(temp, old_path, old_engine, old_engine_url, clients):
    for client in clients.values():
        client.close()
    if repository._engine is not None:
        repository._engine.dispose()
    repository.path = old_path
    repository._engine = old_engine
    repository._engine_url = old_engine_url
    temp.cleanup()


def test_owner_and_admin_can_list_active_hr_role_assignments():
    temp, old_path, old_engine, old_engine_url, workspace, clients = setup_case()
    try:
        repository.assign_organization_human_role(
            workspace_id=workspace["id"],
            actor_user_id="USR-owner",
            target_user_id="USR-member",
            human_role="hr_recruiter",
        )
        for actor in ("USR-owner", "USR-admin"):
            response = clients[actor].get(
                f"/api/v1/workspaces/organizations/{workspace['id']}/human-roles"
            )
            assert response.status_code == 200
            assert response.json() == {
                "workspaceId": workspace["id"],
                "assignments": [{"userId": "USR-member", "humanRole": "hr_recruiter"}],
            }
    finally:
        teardown_case(temp, old_path, old_engine, old_engine_url, clients)


def test_member_is_forbidden_and_outsider_cannot_probe_hr_assignments():
    temp, old_path, old_engine, old_engine_url, workspace, clients = setup_case()
    try:
        assert clients["USR-member"].get(
            f"/api/v1/workspaces/organizations/{workspace['id']}/human-roles"
        ).status_code == 403
        assert clients["USR-outsider"].get(
            f"/api/v1/workspaces/organizations/{workspace['id']}/human-roles"
        ).status_code == 404
    finally:
        teardown_case(temp, old_path, old_engine, old_engine_url, clients)


def test_owner_and_admin_can_assign_multiple_hr_roles_to_active_member():
    temp, old_path, old_engine, old_engine_url, workspace, clients = setup_case()
    try:
        first = clients["USR-owner"].post(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members/USR-member/human-roles",
            json={"humanRole": "hr_recruiter"},
        )
        second = clients["USR-admin"].post(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members/USR-member/human-roles",
            json={"humanRole": "hr_reviewer"},
        )
        assert first.status_code == 201
        assert second.status_code == 201
        roles = repository.list_organization_human_roles(
            workspace["id"], user_id="USR-member"
        )
        assert {row["human_role"] for row in roles} == {"hr_recruiter", "hr_reviewer"}
    finally:
        teardown_case(temp, old_path, old_engine, old_engine_url, clients)


def test_member_cannot_assign_and_outsider_cannot_probe_assignment_route():
    temp, old_path, old_engine, old_engine_url, workspace, clients = setup_case()
    try:
        assert clients["USR-member"].post(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members/USR-member/human-roles",
            json={"humanRole": "hr_recruiter"},
        ).status_code == 403
        assert clients["USR-outsider"].post(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members/USR-member/human-roles",
            json={"humanRole": "hr_recruiter"},
        ).status_code == 404
    finally:
        teardown_case(temp, old_path, old_engine, old_engine_url, clients)


def test_assignment_rejects_inactive_target_member():
    temp, old_path, old_engine, old_engine_url, workspace, clients = setup_case()
    try:
        membership = repository.get_organization_membership(workspace["id"], "USR-member")
        repository.save_organization_membership({**membership, "active": False})
        response = clients["USR-owner"].post(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members/USR-member/human-roles",
            json={"humanRole": "hr_approver"},
        )
        assert response.status_code == 403
    finally:
        teardown_case(temp, old_path, old_engine, old_engine_url, clients)


def test_invalid_hr_role_payload_is_rejected_before_storage():
    temp, old_path, old_engine, old_engine_url, workspace, clients = setup_case()
    try:
        response = clients["USR-owner"].post(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members/USR-member/human-roles",
            json={"humanRole": "hr_superuser"},
        )
        assert response.status_code == 422
        assert repository.list_organization_human_roles(
            workspace["id"], user_id="USR-member"
        ) == []
    finally:
        teardown_case(temp, old_path, old_engine, old_engine_url, clients)


def test_owner_can_deactivate_role_idempotently():
    temp, old_path, old_engine, old_engine_url, workspace, clients = setup_case()
    try:
        repository.assign_organization_human_role(
            workspace_id=workspace["id"],
            actor_user_id="USR-owner",
            target_user_id="USR-member",
            human_role="hr_approver",
        )
        endpoint = (
            f"/api/v1/workspaces/organizations/{workspace['id']}"
            "/members/USR-member/human-roles/hr_approver"
        )
        first = clients["USR-owner"].delete(endpoint)
        second = clients["USR-owner"].delete(endpoint)
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["active"] is False
        assert second.json()["active"] is False
    finally:
        teardown_case(temp, old_path, old_engine, old_engine_url, clients)


def test_deactivate_rejects_unknown_role_and_member_actor():
    temp, old_path, old_engine, old_engine_url, workspace, clients = setup_case()
    try:
        assert clients["USR-owner"].delete(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members/USR-member/human-roles/not-a-role"
        ).status_code == 422
        assert clients["USR-member"].delete(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members/USR-member/human-roles/hr_recruiter"
        ).status_code == 403
    finally:
        teardown_case(temp, old_path, old_engine, old_engine_url, clients)
