"""Phase 4.4.4 adversarial HR human-role verification.

These tests exercise direct API and authorization-resolver attempts so the
backend remains authoritative even when frontend controls are bypassed.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.security.hr_roles import (
    HRHumanPermission,
    resolve_hr_human_authorization,
)
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
    path = str(Path(temp.name) / "hr-role-adversarial.db")
    old_path = repository.path
    old_engine = repository._engine
    old_engine_url = repository._engine_url

    repository.path = path
    repository._engine = None
    repository._engine_url = None
    repository.initialize()

    user_ids = (
        "USR-owner-a",
        "USR-admin-a",
        "USR-member-a",
        "USR-owner-b",
        "USR-member-b",
        "USR-outsider",
    )
    for user_id in user_ids:
        repository.save_user(_user(user_id))
        repository.ensure_personal_workspace(user_id)

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

    org_b, code_b = repository.create_organization(
        creator_user_id="USR-owner-b",
        name="External Org",
    )
    repository.join_organization(user_id="USR-member-b", join_code=code_b)
    code_b = repository.manage_organization_invites(workspace_id=org_b["id"], user_id="USR-owner-b", action="generate")["joinCode"]
    repository.join_organization(user_id="USR-member-a", join_code=code_b)

    clients = {user_id: _session_client(user_id) for user_id in user_ids}
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


def test_member_cannot_self_assign_hr_role_through_direct_api_call():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, org_a, _, clients = case
    try:
        response = clients["USR-member-a"].post(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members/USR-member-a/human-roles",
            json={"humanRole": "hr_approver"},
        )
        assert response.status_code == 403
        assert repository.list_organization_human_roles(
            org_a["id"], user_id="USR-member-a"
        ) == []
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)


def test_owner_of_one_organization_cannot_manage_hr_roles_in_another():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, _, org_b, clients = case
    try:
        response = clients["USR-owner-a"].post(
            f"/api/v1/workspaces/organizations/{org_b['id']}/members/USR-member-b/human-roles",
            json={"humanRole": "hr_recruiter"},
        )
        assert response.status_code == 404
        assert repository.list_organization_human_roles(
            org_b["id"], user_id="USR-member-b"
        ) == []
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)


def test_outsider_cannot_probe_hr_role_listing_or_assignment_routes():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, org_a, _, clients = case
    try:
        listing = clients["USR-outsider"].get(
            f"/api/v1/workspaces/organizations/{org_a['id']}/human-roles"
        )
        assignment = clients["USR-outsider"].post(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members/USR-member-a/human-roles",
            json={"humanRole": "hr_reviewer"},
        )
        assert listing.status_code == 404
        assert assignment.status_code == 404
        assert "USR-member-a" not in listing.text
        assert repository.list_organization_human_roles(
            org_a["id"], user_id="USR-member-a"
        ) == []
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)


def test_admin_demotion_revokes_hr_role_management_immediately():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, org_a, _, clients = case
    try:
        before = clients["USR-admin-a"].post(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members/USR-member-a/human-roles",
            json={"humanRole": "hr_recruiter"},
        )
        assert before.status_code == 201

        demote = clients["USR-owner-a"].patch(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members/USR-admin-a/role",
            json={"membershipRole": "member"},
        )
        assert demote.status_code == 200

        after = clients["USR-admin-a"].post(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members/USR-member-a/human-roles",
            json={"humanRole": "hr_reviewer"},
        )
        assert after.status_code == 403
        roles = repository.list_organization_human_roles(
            org_a["id"], user_id="USR-member-a"
        )
        assert {row["human_role"] for row in roles} == {"hr_recruiter"}
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)


def test_inactive_admin_membership_revokes_hr_management_with_live_session():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, org_a, _, clients = case
    try:
        membership = repository.get_organization_membership(org_a["id"], "USR-admin-a")
        repository.save_organization_membership({**membership, "active": False})

        response = clients["USR-admin-a"].get(
            f"/api/v1/workspaces/organizations/{org_a['id']}/human-roles"
        )
        assert response.status_code == 404
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)


def test_hr_role_deactivation_revokes_domain_permission_immediately():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, org_a, _, clients = case
    try:
        assigned = clients["USR-owner-a"].post(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members/USR-member-a/human-roles",
            json={"humanRole": "hr_reviewer"},
        )
        assert assigned.status_code == 201

        before = resolve_hr_human_authorization(
            repository,
            user_id="USR-member-a",
            workspace_id=org_a["id"],
        )
        assert before.allows(HRHumanPermission.JD_REVIEW)
        assert before.allows(HRHumanPermission.JD_REQUEST_REVISION)

        removed = clients["USR-owner-a"].delete(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members/USR-member-a/human-roles/hr_reviewer"
        )
        assert removed.status_code == 200

        after = resolve_hr_human_authorization(
            repository,
            user_id="USR-member-a",
            workspace_id=org_a["id"],
        )
        assert not after.allows(HRHumanPermission.JD_REVIEW)
        assert not after.allows(HRHumanPermission.JD_REQUEST_REVISION)
        assert after.roles == frozenset()
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)


def test_inactive_target_membership_invalidates_existing_hr_permissions():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, org_a, _, clients = case
    try:
        assigned = clients["USR-owner-a"].post(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members/USR-member-a/human-roles",
            json={"humanRole": "hr_approver"},
        )
        assert assigned.status_code == 201

        before = resolve_hr_human_authorization(
            repository,
            user_id="USR-member-a",
            workspace_id=org_a["id"],
        )
        assert before.allows(HRHumanPermission.JD_APPROVE)

        membership = repository.get_organization_membership(org_a["id"], "USR-member-a")
        repository.save_organization_membership({**membership, "active": False})

        after = resolve_hr_human_authorization(
            repository,
            user_id="USR-member-a",
            workspace_id=org_a["id"],
        )
        assert after.roles == frozenset()
        assert not after.allows(HRHumanPermission.JD_APPROVE)
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)


def test_hr_roles_are_isolated_between_organizations_for_same_user():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, org_a, org_b, clients = case
    try:
        assigned = clients["USR-owner-a"].post(
            f"/api/v1/workspaces/organizations/{org_a['id']}/members/USR-member-a/human-roles",
            json={"humanRole": "hr_recruiter"},
        )
        assert assigned.status_code == 201

        auth_a = resolve_hr_human_authorization(
            repository,
            user_id="USR-member-a",
            workspace_id=org_a["id"],
        )
        auth_b = resolve_hr_human_authorization(
            repository,
            user_id="USR-member-a",
            workspace_id=org_b["id"],
        )
        assert auth_a.allows(HRHumanPermission.HIRING_REQUEST_MANAGE)
        assert not auth_b.allows(HRHumanPermission.HIRING_REQUEST_MANAGE)
        assert auth_b.roles == frozenset()
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)


def test_personal_workspace_cannot_be_used_as_hr_role_management_scope():
    case = _setup()
    temp, old_path, old_engine, old_engine_url, _, _, clients = case
    try:
        personal = repository.get_personal_workspace("USR-owner-a")
        listing = clients["USR-owner-a"].get(
            f"/api/v1/workspaces/organizations/{personal['id']}/human-roles"
        )
        assignment = clients["USR-owner-a"].post(
            f"/api/v1/workspaces/organizations/{personal['id']}/members/USR-owner-a/human-roles",
            json={"humanRole": "hr_recruiter"},
        )
        assert listing.status_code == 403
        assert assignment.status_code == 403
        assert resolve_hr_human_authorization(
            repository,
            user_id="USR-owner-a",
            workspace_id=personal["id"],
        ).roles == frozenset()
    finally:
        _teardown(temp, old_path, old_engine, old_engine_url, clients)
