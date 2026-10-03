"""Phase 4.2.5 Create Organization API tests."""

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
from app.security.workspaces import (
    join_code_digest,
)
from app.storage import models as dbm
from app.storage.database import repository


def make_user():
    now = datetime.now(
        timezone.utc
    ).isoformat()

    return {
        "id": "USR-create-org",
        "google_sub": "google-create-org",
        "email": "creator@example.com",
        "display_name": "Creator",
        "profile_picture": None,
        "email_verified": True,
        "active": True,
        "created_at": now,
        "last_login_at": now,
    }


def authenticated_client():
    temp = tempfile.TemporaryDirectory()
    path = str(
        Path(temp.name)
        / "create-org.db"
    )

    old_path = repository.path
    old_engine = repository._engine
    old_engine_url = repository._engine_url

    repository.path = path
    repository._engine = None
    repository._engine_url = None
    repository.initialize()

    user = make_user()
    repository.save_user(user)
    repository.ensure_personal_workspace(
        user["id"]
    )

    token = create_opaque_token()
    now = datetime.now(
        timezone.utc
    ).isoformat()

    repository.save_auth_session(
        {
            "id": "SES-create-org",
            "user_id": user["id"],
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

    client = TestClient(app)
    client.cookies.set(
        "app_session",
        token,
    )

    return (
        client,
        user,
        temp,
        old_path,
        old_engine,
        old_engine_url,
    )


def cleanup_client(
    client,
    temp,
    old_path,
    old_engine,
    old_engine_url,
):
    client.close()

    if repository._engine is not None:
        repository._engine.dispose()

    repository.path = old_path
    repository._engine = old_engine
    repository._engine_url = old_engine_url

    temp.cleanup()


def test_create_organization_requires_authentication():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workspaces/organizations",
            json={
                "name": "Example Company"
            },
        )

    assert response.status_code == 401


def test_create_organization_returns_owner_and_join_code():
    (
        client,
        user,
        temp,
        old_path,
        old_engine,
        old_engine_url,
    ) = authenticated_client()

    try:
        response = client.post(
            "/api/v1/workspaces/organizations",
            json={
                "name": "  Example   Company  "
            },
        )

        assert response.status_code == 201

        body = response.json()

        assert body["kind"] == "organization"
        assert body["name"] == "Example Company"
        assert body["membershipRole"] == "owner"

        join_code = body["joinCode"]

        assert len(join_code.split("-")) == 3
        assert all(
            len(group) == 4
            for group in join_code.split("-")
        )

        workspace = repository.get_workspace(
            body["id"]
        )

        assert workspace is not None
        assert workspace["kind"] == "organization"
        assert (
            workspace["created_by_user_id"]
            == user["id"]
        )

        membership = (
            repository.get_organization_membership(
                body["id"],
                user["id"],
            )
        )

        assert membership is not None
        assert (
            membership["membership_role"]
            == "owner"
        )

    finally:
        cleanup_client(
            client,
            temp,
            old_path,
            old_engine,
            old_engine_url,
        )


def test_plain_join_code_is_never_persisted():
    (
        client,
        _,
        temp,
        old_path,
        old_engine,
        old_engine_url,
    ) = authenticated_client()

    try:
        response = client.post(
            "/api/v1/workspaces/organizations",
            json={
                "name": "Secure Company"
            },
        )

        assert response.status_code == 201

        body = response.json()
        join_code = body["joinCode"]

        workspace = repository.get_workspace(
            body["id"]
        )

        assert (
            workspace["join_code_digest"]
            == join_code_digest(join_code)
        )

        serialized = str(workspace)

        assert join_code not in serialized

    finally:
        cleanup_client(
            client,
            temp,
            old_path,
            old_engine,
            old_engine_url,
        )


def test_two_organizations_receive_different_join_codes():
    (
        client,
        _,
        temp,
        old_path,
        old_engine,
        old_engine_url,
    ) = authenticated_client()

    try:
        first = client.post(
            "/api/v1/workspaces/organizations",
            json={
                "name": "First Company"
            },
        )

        second = client.post(
            "/api/v1/workspaces/organizations",
            json={
                "name": "Second Company"
            },
        )

        assert first.status_code == 201
        assert second.status_code == 201

        assert (
            first.json()["joinCode"]
            != second.json()["joinCode"]
        )

    finally:
        cleanup_client(
            client,
            temp,
            old_path,
            old_engine,
            old_engine_url,
        )


def test_invalid_organization_name_is_rejected():
    (
        client,
        _,
        temp,
        old_path,
        old_engine,
        old_engine_url,
    ) = authenticated_client()

    try:
        response = client.post(
            "/api/v1/workspaces/organizations",
            json={
                "name": " "
            },
        )

        assert response.status_code == 422

        with repository.engine.connect() as connection:
            organizations = connection.execute(
                select(
                    dbm.workspaces
                ).where(
                    dbm.workspaces.c.kind
                    == "organization"
                )
            ).all()

        assert organizations == []

    finally:
        cleanup_client(
            client,
            temp,
            old_path,
            old_engine,
            old_engine_url,
        )


def test_create_does_not_expose_other_organizations():
    (
        client,
        _,
        temp,
        old_path,
        old_engine,
        old_engine_url,
    ) = authenticated_client()

    try:
        response = client.post(
            "/api/v1/workspaces/organizations",
            json={
                "name": "Private Company"
            },
        )

        assert response.status_code == 201

        body = response.json()

        # The creation response contains only the newly created organization.
        assert "organizations" not in body
        assert "organizationCount" not in body
        assert "existingOrganizations" not in body

    finally:
        cleanup_client(
            client,
            temp,
            old_path,
            old_engine,
            old_engine_url,
        )
