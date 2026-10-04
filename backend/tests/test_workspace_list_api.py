"""Phase 4.2.6A authenticated workspace-discovery API tests."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.security.session import (
    create_opaque_token,
    session_expiry,
    token_digest,
)
from app.storage.database import repository


def now_text():
    return datetime.now(timezone.utc).isoformat()


def make_user(user_id: str):
    now = now_text()
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


def make_organization(owner_id: str, workspace_id: str, name: str, *, active: bool = True):
    now = now_text()
    return {
        "id": workspace_id,
        "kind": "organization",
        "name": name,
        "personal_owner_user_id": None,
        "created_by_user_id": owner_id,
        "join_code_digest": None,
        "active": active,
        "created_at": now,
        "updated_at": now,
    }


def make_membership(workspace_id: str, user_id: str, *, role: str = "member", active: bool = True, added_by: str):
    return {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "membership_role": role,
        "active": active,
        "joined_at": now_text(),
        "added_by_user_id": added_by,
    }


def authenticated_client(user_id: str = "USR-current"):
    temp = tempfile.TemporaryDirectory()
    path = str(Path(temp.name) / "workspace-list.db")

    old_path = repository.path
    old_engine = repository._engine
    old_engine_url = repository._engine_url

    repository.path = path
    repository._engine = None
    repository._engine_url = None
    repository.initialize()

    user = make_user(user_id)
    repository.save_user(user)

    token = create_opaque_token()
    repository.save_auth_session(
        {
            "id": f"SES-{user_id}",
            "user_id": user["id"],
            "token_digest": token_digest(token),
            "created_at": now_text(),
            "expires_at": session_expiry().isoformat(),
            "revoked_at": None,
        }
    )

    client = TestClient(app)
    client.cookies.set("app_session", token)

    return client, user, temp, old_path, old_engine, old_engine_url


def cleanup_client(client, temp, old_path, old_engine, old_engine_url):
    client.close()
    if repository._engine is not None:
        repository._engine.dispose()
    repository.path = old_path
    repository._engine = old_engine
    repository._engine_url = old_engine_url
    temp.cleanup()


def test_workspace_list_requires_authentication():
    with TestClient(app) as client:
        response = client.get("/api/v1/workspaces")
    assert response.status_code == 401


def test_user_with_no_organizations_gets_only_personal_workspace():
    ctx = authenticated_client()
    client, user, temp, old_path, old_engine, old_engine_url = ctx
    try:
        response = client.get("/api/v1/workspaces")
        assert response.status_code == 200
        body = response.json()
        assert body["personalWorkspace"]["kind"] == "personal"
        assert body["personalWorkspace"]["name"] == "Personal Workspace"
        assert body["personalWorkspace"]["membershipRole"] is None
        assert body["organizations"] == []
        personal = repository.get_personal_workspace(user["id"])
        assert body["personalWorkspace"]["id"] == personal["id"]
    finally:
        cleanup_client(client, temp, old_path, old_engine, old_engine_url)


def test_owner_and_member_roles_are_returned_for_visible_organizations():
    ctx = authenticated_client()
    client, user, temp, old_path, old_engine, old_engine_url = ctx
    try:
        owner_org, _ = repository.create_organization(
            creator_user_id=user["id"], name="Owner Org"
        )

        other = make_user("USR-other")
        repository.save_user(other)
        member_org = make_organization(other["id"], "WS-member", "Member Org")
        repository.save_workspace(member_org)
        repository.save_organization_membership(
            make_membership(member_org["id"], user["id"], added_by=other["id"])
        )

        response = client.get("/api/v1/workspaces")
        assert response.status_code == 200
        organizations = {item["id"]: item for item in response.json()["organizations"]}
        assert organizations[owner_org["id"]]["membershipRole"] == "owner"
        assert organizations[member_org["id"]]["membershipRole"] == "member"
    finally:
        cleanup_client(client, temp, old_path, old_engine, old_engine_url)


def test_unrelated_and_other_personal_workspaces_are_not_exposed():
    ctx = authenticated_client()
    client, user, temp, old_path, old_engine, old_engine_url = ctx
    try:
        other = make_user("USR-outsider")
        repository.save_user(other)
        other_personal = repository.ensure_personal_workspace(other["id"])
        unrelated_org, _ = repository.create_organization(
            creator_user_id=other["id"], name="Other Org"
        )

        response = client.get("/api/v1/workspaces")
        assert response.status_code == 200
        body = response.json()
        all_ids = {body["personalWorkspace"]["id"]} | {
            item["id"] for item in body["organizations"]
        }
        assert other_personal["id"] not in all_ids
        assert unrelated_org["id"] not in all_ids
        assert body["personalWorkspace"]["id"] == repository.get_personal_workspace(user["id"])["id"]
    finally:
        cleanup_client(client, temp, old_path, old_engine, old_engine_url)


def test_inactive_membership_and_inactive_organization_are_excluded():
    ctx = authenticated_client()
    client, user, temp, old_path, old_engine, old_engine_url = ctx
    try:
        actor = make_user("USR-actor")
        repository.save_user(actor)

        inactive_membership_org = make_organization(actor["id"], "WS-inactive-member", "Inactive Membership")
        repository.save_workspace(inactive_membership_org)
        repository.save_organization_membership(
            make_membership(
                inactive_membership_org["id"], user["id"], active=False, added_by=actor["id"]
            )
        )

        inactive_org = make_organization(actor["id"], "WS-inactive-org", "Inactive Org")
        repository.save_workspace(inactive_org)
        repository.save_organization_membership(
            make_membership(inactive_org["id"], user["id"], added_by=actor["id"])
        )
        inactive_org["active"] = False
        inactive_org["updated_at"] = now_text()
        repository.save_workspace(inactive_org)

        response = client.get("/api/v1/workspaces")
        assert response.status_code == 200
        ids = {item["id"] for item in response.json()["organizations"]}
        assert inactive_membership_org["id"] not in ids
        assert inactive_org["id"] not in ids
    finally:
        cleanup_client(client, temp, old_path, old_engine, old_engine_url)


def test_response_does_not_expose_private_workspace_fields():
    ctx = authenticated_client()
    client, user, temp, old_path, old_engine, old_engine_url = ctx
    try:
        repository.create_organization(
            creator_user_id=user["id"], name="Private Fields Org"
        )
        response = client.get("/api/v1/workspaces")
        assert response.status_code == 200
        body = response.json()
        serialized = response.text

        assert "joinCode" not in serialized
        assert "joinCodeDigest" not in serialized
        assert "createdByUserId" not in serialized
        assert "personalOwnerUserId" not in serialized
        assert "addedByUserId" not in serialized
        assert set(body) == {"personalWorkspace", "organizations"}
    finally:
        cleanup_client(client, temp, old_path, old_engine, old_engine_url)
