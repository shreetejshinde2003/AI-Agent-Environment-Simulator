"""Phase 4.2.6 Join Organization API tests."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.security.session import (
    create_opaque_token,
    session_expiry,
    token_digest,
)
from app.storage import models as dbm
from app.storage.database import repository


def make_user(
    user_id: str,
    google_sub: str,
):
    now = datetime.now(
        timezone.utc
    ).isoformat()

    return {
        "id": user_id,
        "google_sub": google_sub,
        "email": (
            f"{user_id.lower()}@example.com"
        ),
        "display_name": user_id,
        "profile_picture": None,
        "email_verified": True,
        "active": True,
        "created_at": now,
        "last_login_at": now,
    }


def save_session(
    user_id: str,
    session_id: str,
):
    token = create_opaque_token()
    now = datetime.now(
        timezone.utc
    ).isoformat()

    repository.save_auth_session(
        {
            "id": session_id,
            "user_id": user_id,
            "token_digest": token_digest(
                token
            ),
            "created_at": now,
            "expires_at": (
                session_expiry().isoformat()
            ),
            "revoked_at": None,
        }
    )

    return token


def setup_environment():
    temp = tempfile.TemporaryDirectory()

    path = str(
        Path(temp.name)
        / "join-org.db"
    )

    old_path = repository.path
    old_engine = repository._engine
    old_engine_url = repository._engine_url

    repository.path = path
    repository._engine = None
    repository._engine_url = None
    repository.initialize()

    owner = make_user(
        "USR-owner",
        "google-owner",
    )

    member = make_user(
        "USR-member",
        "google-member",
    )

    outsider = make_user(
        "USR-outsider",
        "google-outsider",
    )

    for user in (
        owner,
        member,
        outsider,
    ):
        repository.save_user(user)
        repository.ensure_personal_workspace(
            user["id"]
        )

    organization, join_code = (
        repository.create_organization(
            creator_user_id=owner["id"],
            name="Example Company",
        )
    )

    return {
        "temp": temp,
        "old_path": old_path,
        "old_engine": old_engine,
        "old_engine_url": old_engine_url,
        "owner": owner,
        "member": member,
        "outsider": outsider,
        "organization": organization,
        "join_code": join_code,
    }


def cleanup_environment(state):
    if repository._engine is not None:
        repository._engine.dispose()

    repository.path = state["old_path"]
    repository._engine = state["old_engine"]
    repository._engine_url = state[
        "old_engine_url"
    ]

    state["temp"].cleanup()


def client_for(
    user,
    session_id,
):
    token = save_session(
        user["id"],
        session_id,
    )

    client = TestClient(app)

    client.cookies.set(
        "app_session",
        token,
    )

    return client


def test_join_requires_authentication(isolated_startup_repository):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workspaces/organizations/join",
            json={
                "joinCode": "ABCD-EFGH-JKLM"
            },
        )

    assert response.status_code == 401


def test_valid_code_adds_member():
    state = setup_environment()

    client = client_for(
        state["member"],
        "SES-member",
    )

    try:
        response = client.post(
            "/api/v1/workspaces/organizations/join",
            json={
                "joinCode": state[
                    "join_code"
                ]
            },
        )

        assert response.status_code == 200

        body = response.json()

        assert (
            body["id"]
            == state["organization"]["id"]
        )
        assert body["kind"] == "organization"
        assert (
            body["name"]
            == "Example Company"
        )
        assert (
            body["membershipRole"]
            == "member"
        )

        membership = (
            repository.get_organization_membership(
                state["organization"]["id"],
                state["member"]["id"],
            )
        )

        assert membership is not None
        assert membership["active"] is True
        assert (
            membership["membership_role"]
            == "member"
        )

    finally:
        client.close()
        cleanup_environment(state)


def test_join_code_is_case_insensitive():
    state = setup_environment()

    client = client_for(
        state["member"],
        "SES-lowercase",
    )

    try:
        response = client.post(
            "/api/v1/workspaces/organizations/join",
            json={
                "joinCode": (
                    state["join_code"]
                    .lower()
                )
            },
        )

        assert response.status_code == 200

    finally:
        client.close()
        cleanup_environment(state)


def test_invalid_code_does_not_disclose_organization():
    state = setup_environment()

    client = client_for(
        state["outsider"],
        "SES-invalid",
    )

    try:
        response = client.post(
            "/api/v1/workspaces/organizations/join",
            json={
                "joinCode": "AAAA-BBBB-CCCC"
            },
        )

        assert response.status_code == 404

        body = response.json()

        assert (
            body["detail"]["code"]
            == "invalid_join_code"
        )

        serialized = str(body)

        assert "Example Company" not in serialized
        assert (
            state["organization"]["id"]
            not in serialized
        )

    finally:
        client.close()
        cleanup_environment(state)


def test_consumed_invite_cannot_be_reused():
    state = setup_environment()

    client = client_for(
        state["member"],
        "SES-repeat",
    )

    try:
        first = client.post(
            "/api/v1/workspaces/organizations/join",
            json={
                "joinCode": state[
                    "join_code"
                ]
            },
        )

        second = client.post(
            "/api/v1/workspaces/organizations/join",
            json={
                "joinCode": state[
                    "join_code"
                ]
            },
        )

        assert first.status_code == 200
        assert second.status_code == 404

        with repository.engine.connect() as connection:
            rows = connection.execute(
                select(
                    dbm.organization_memberships
                ).where(
                    dbm.organization_memberships.c.workspace_id
                    == state["organization"]["id"],
                    dbm.organization_memberships.c.user_id
                    == state["member"]["id"],
                )
            ).all()

        assert len(rows) == 1

    finally:
        client.close()
        cleanup_environment(state)


def test_owner_rejoining_does_not_become_member():
    state = setup_environment()

    client = client_for(
        state["owner"],
        "SES-owner",
    )

    try:
        response = client.post(
            "/api/v1/workspaces/organizations/join",
            json={
                "joinCode": state[
                    "join_code"
                ]
            },
        )

        assert response.status_code == 200
        assert (
            response.json()[
                "membershipRole"
            ]
            == "owner"
        )

        membership = (
            repository.get_organization_membership(
                state["organization"]["id"],
                state["owner"]["id"],
            )
        )

        assert (
            membership["membership_role"]
            == "owner"
        )

    finally:
        client.close()
        cleanup_environment(state)


def test_inactive_membership_is_reactivated():
    state = setup_environment()

    repository.save_organization_membership(
        {
            "workspace_id": (
                state["organization"]["id"]
            ),
            "user_id": state["member"]["id"],
            "membership_role": "member",
            "active": False,
            "joined_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "added_by_user_id": (
                state["owner"]["id"]
            ),
        }
    )

    client = client_for(
        state["member"],
        "SES-reactivate",
    )

    try:
        response = client.post(
            "/api/v1/workspaces/organizations/join",
            json={
                "joinCode": state[
                    "join_code"
                ]
            },
        )

        assert response.status_code == 200

        membership = (
            repository.get_organization_membership(
                state["organization"]["id"],
                state["member"]["id"],
            )
        )

        assert membership["active"] is True

    finally:
        client.close()
        cleanup_environment(state)


def test_inactive_organization_code_is_unavailable():
    state = setup_environment()

    workspace = dict(
        state["organization"],
        active=False,
    )

    repository.save_workspace(
        workspace
    )

    client = client_for(
        state["member"],
        "SES-inactive-org",
    )

    try:
        response = client.post(
            "/api/v1/workspaces/organizations/join",
            json={
                "joinCode": state[
                    "join_code"
                ]
            },
        )

        assert response.status_code == 404

        assert (
            response.json()["detail"]["code"]
            == "invalid_join_code"
        )

    finally:
        client.close()
        cleanup_environment(state)


def test_join_response_does_not_expose_other_organizations():
    state = setup_environment()

    repository.create_organization(
        creator_user_id=state["owner"]["id"],
        name="Hidden Second Company",
    )

    client = client_for(
        state["member"],
        "SES-private",
    )

    try:
        response = client.post(
            "/api/v1/workspaces/organizations/join",
            json={
                "joinCode": state[
                    "join_code"
                ]
            },
        )

        assert response.status_code == 200

        body = response.json()
        serialized = str(body)

        assert "Hidden Second Company" not in serialized
        assert "organizations" not in body
        assert "organizationCount" not in body

    finally:
        client.close()
        cleanup_environment(state)
