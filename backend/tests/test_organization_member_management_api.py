"""Phase 4.3.3 organization member-management API tests."""

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
    path = str(Path(temp.name) / "members-api.db")
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

    return (
        temp, old_path, old_engine, old_engine_url, workspace, clients
    )


def teardown_case(temp, old_path, old_engine, old_engine_url, clients):
    for client in clients.values():
        client.close()
    if repository._engine is not None:
        repository._engine.dispose()
    repository.path = old_path
    repository._engine = old_engine
    repository._engine_url = old_engine_url
    temp.cleanup()


def test_owner_and_admin_can_list_active_members_without_google_identity_leak():
    temp, old_path, old_engine, old_engine_url, workspace, clients = setup_case()
    try:
        for actor in ("USR-owner", "USR-admin"):
            response = clients[actor].get(
                f"/api/v1/workspaces/organizations/{workspace['id']}/members"
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["workspaceId"] == workspace["id"]
            assert {m["membershipRole"] for m in payload["members"]} == {
                "owner", "admin", "member"
            }
            serialized = response.text
            assert "google_sub" not in serialized
            assert "googleSub" not in serialized
            assert "joinCode" not in serialized
    finally:
        teardown_case(temp, old_path, old_engine, old_engine_url, clients)


def test_member_cannot_list_members_and_outsider_cannot_probe_workspace():
    temp, old_path, old_engine, old_engine_url, workspace, clients = setup_case()
    try:
        member = clients["USR-member"].get(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members"
        )
        assert member.status_code == 403

        outsider = clients["USR-outsider"].get(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members"
        )
        assert outsider.status_code == 404
    finally:
        teardown_case(temp, old_path, old_engine, old_engine_url, clients)


def test_owner_can_promote_member_to_admin_and_workspace_discovery_accepts_admin():
    temp, old_path, old_engine, old_engine_url, workspace, clients = setup_case()
    try:
        response = clients["USR-owner"].patch(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members/USR-member/role",
            json={"membershipRole": "admin"},
        )
        assert response.status_code == 200
        assert response.json()["membershipRole"] == "admin"

        discovery = clients["USR-member"].get("/api/v1/workspaces")
        assert discovery.status_code == 200
        org = next(
            item for item in discovery.json()["organizations"]
            if item["id"] == workspace["id"]
        )
        assert org["membershipRole"] == "admin"
    finally:
        teardown_case(temp, old_path, old_engine, old_engine_url, clients)


def test_admin_can_change_member_role_only_within_admin_policy():
    temp, old_path, old_engine, old_engine_url, workspace, clients = setup_case()
    try:
        promote = clients["USR-admin"].patch(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members/USR-member/role",
            json={"membershipRole": "admin"},
        )
        assert promote.status_code == 403

        no_op_member = clients["USR-admin"].patch(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members/USR-member/role",
            json={"membershipRole": "member"},
        )
        assert no_op_member.status_code == 200
    finally:
        teardown_case(temp, old_path, old_engine, old_engine_url, clients)


def test_member_and_outsider_cannot_change_roles():
    temp, old_path, old_engine, old_engine_url, workspace, clients = setup_case()
    try:
        denied = clients["USR-member"].patch(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members/USR-admin/role",
            json={"membershipRole": "member"},
        )
        assert denied.status_code == 403

        hidden = clients["USR-outsider"].patch(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members/USR-member/role",
            json={"membershipRole": "admin"},
        )
        assert hidden.status_code == 404
    finally:
        teardown_case(temp, old_path, old_engine, old_engine_url, clients)


def test_last_owner_protection_surfaces_as_conflict():
    temp, old_path, old_engine, old_engine_url, workspace, clients = setup_case()
    try:
        response = clients["USR-owner"].patch(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members/USR-owner/role",
            json={"membershipRole": "admin"},
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "role_change_conflict"
    finally:
        teardown_case(temp, old_path, old_engine, old_engine_url, clients)


def test_role_payload_rejects_unknown_role_before_storage():
    temp, old_path, old_engine, old_engine_url, workspace, clients = setup_case()
    try:
        response = clients["USR-owner"].patch(
            f"/api/v1/workspaces/organizations/{workspace['id']}/members/USR-member/role",
            json={"membershipRole": "superadmin"},
        )
        assert response.status_code == 422
    finally:
        teardown_case(temp, old_path, old_engine, old_engine_url, clients)
