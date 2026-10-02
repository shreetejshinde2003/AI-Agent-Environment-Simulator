"""Google authentication API contract tests.

All provider calls and Google ID-token verification are mocked.
No real Google request is made.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.api.routes import auth
from app.main import app
from app.storage.database import repository


@pytest.fixture
def isolated_auth_db():
    temp = tempfile.TemporaryDirectory()
    path = str(
        Path(temp.name) / "auth-api.db"
    )

    old_path = repository.path
    old_engine = repository._engine
    old_engine_url = repository._engine_url

    repository.path = path
    repository._engine = None
    repository._engine_url = None
    repository.initialize()

    yield

    if repository._engine is not None:
        repository._engine.dispose()

    repository.path = old_path
    repository._engine = old_engine
    repository._engine_url = old_engine_url

    temp.cleanup()


@pytest.fixture
def google_settings():
    with (
        patch.object(
            auth.settings,
            "GOOGLE_CLIENT_ID",
            "test-client-id",
        ),
        patch.object(
            auth.settings,
            "GOOGLE_CLIENT_SECRET",
            "test-client-secret",
        ),
        patch.object(
            auth.settings,
            "GOOGLE_REDIRECT_URI",
            (
                "http://localhost:8000"
                "/api/v1/auth/google/callback"
            ),
        ),
        patch.object(
            auth.settings,
            "FRONTEND_URL",
            "http://localhost:5173",
        ),
    ):
        yield


def begin_login(client):
    response = client.get(
        "/api/v1/auth/google/login",
        follow_redirects=False,
    )

    assert response.status_code == 302

    parsed = urlparse(
        response.headers["location"]
    )

    query = parse_qs(
        parsed.query
    )

    return response, query


def test_google_login_builds_state_nonce_and_pkce(
    isolated_auth_db,
    google_settings,
):
    with TestClient(app) as client:
        response, query = begin_login(
            client
        )

        assert (
            parsed_host := urlparse(
                response.headers["location"]
            ).netloc
        ) == "accounts.google.com"

        assert query["client_id"] == [
            "test-client-id"
        ]

        assert query["response_type"] == [
            "code"
        ]

        assert query["scope"] == [
            "openid email profile"
        ]

        assert query[
            "code_challenge_method"
        ] == ["S256"]

        assert query["state"]
        assert query["nonce"]
        assert query["code_challenge"]

        assert client.cookies.get(
            "oauth_state"
        )

        assert client.cookies.get(
            "oauth_nonce"
        )

        assert client.cookies.get(
            "oauth_pkce"
        )


def test_callback_creates_local_user_and_session(
    isolated_auth_db,
    google_settings,
):
    with (
        patch.object(
            auth,
            "_exchange_code",
            new_callable=AsyncMock,
            return_value={
                "id_token": "mock-id-token",
                "access_token": "provider-token-not-persisted",
            },
        ) as exchange,
        patch.object(
            auth,
            "_verify_google_id_token",
        ) as verify,
        TestClient(app) as client,
    ):
        _, query = begin_login(
            client
        )

        state = query["state"][0]
        nonce = query["nonce"][0]

        verify.return_value = {
            "sub": "google-user-123",
            "email": "person@example.com",
            "email_verified": True,
            "name": "Test Person",
            "picture": (
                "https://example.com/avatar.png"
            ),
            "nonce": nonce,
        }

        response = client.get(
            (
                "/api/v1/auth/google/callback"
                f"?code=authorization-code"
                f"&state={state}"
            ),
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert (
            response.headers["location"]
            == "http://localhost:5173/?auth=success"
        )

        exchange.assert_awaited_once()
        verify.assert_called_once_with(
            "mock-id-token"
        )

        user = (
            repository
            .get_user_by_google_sub(
                "google-user-123"
            )
        )

        assert user is not None
        assert (
            user["email"]
            == "person@example.com"
        )

        session_token = client.cookies.get(
            "app_session"
        )

        assert session_token
        assert (
            "provider-token-not-persisted"
            != session_token
        )


def test_me_reads_valid_application_session(
    isolated_auth_db,
    google_settings,
):
    with (
        patch.object(
            auth,
            "_exchange_code",
            new_callable=AsyncMock,
            return_value={
                "id_token": "mock-id-token"
            },
        ),
        patch.object(
            auth,
            "_verify_google_id_token",
        ) as verify,
        TestClient(app) as client,
    ):
        _, query = begin_login(
            client
        )

        state = query["state"][0]
        nonce = query["nonce"][0]

        verify.return_value = {
            "sub": "google-user-me",
            "email": "me@example.com",
            "email_verified": True,
            "name": "Me User",
            "nonce": nonce,
        }

        callback = client.get(
            (
                "/api/v1/auth/google/callback"
                f"?code=code"
                f"&state={state}"
            ),
            follow_redirects=False,
        )

        assert callback.status_code == 302

        response = client.get(
            "/api/v1/auth/me"
        )

        assert response.status_code == 200

        body = response.json()

        assert body["authenticated"] is True
        assert (
            body["user"]["email"]
            == "me@example.com"
        )
        assert (
            body["user"]["displayName"]
            == "Me User"
        )


def test_logout_revokes_session(
    isolated_auth_db,
    google_settings,
):
    with (
        patch.object(
            auth,
            "_exchange_code",
            new_callable=AsyncMock,
            return_value={
                "id_token": "mock-id-token"
            },
        ),
        patch.object(
            auth,
            "_verify_google_id_token",
        ) as verify,
        TestClient(app) as client,
    ):
        _, query = begin_login(
            client
        )

        state = query["state"][0]
        nonce = query["nonce"][0]

        verify.return_value = {
            "sub": "google-user-logout",
            "email": "logout@example.com",
            "email_verified": True,
            "name": "Logout User",
            "nonce": nonce,
        }

        client.get(
            (
                "/api/v1/auth/google/callback"
                f"?code=code"
                f"&state={state}"
            ),
            follow_redirects=False,
        )

        assert (
            client.get(
                "/api/v1/auth/me"
            ).status_code
            == 200
        )

        logout = client.post(
            "/api/v1/auth/logout"
        )

        assert logout.status_code == 204

        assert (
            client.get(
                "/api/v1/auth/me"
            ).status_code
            == 401
        )


def test_callback_rejects_wrong_state_without_provider_call(
    isolated_auth_db,
    google_settings,
):
    with (
        patch.object(
            auth,
            "_exchange_code",
            new_callable=AsyncMock,
        ) as exchange,
        TestClient(app) as client,
    ):
        begin_login(client)

        response = client.get(
            (
                "/api/v1/auth/google/callback"
                "?code=code"
                "&state=attacker-state"
            ),
            follow_redirects=False,
        )

        assert response.status_code == 400
        assert (
            response.json()["detail"]["code"]
            == "invalid_oauth_state"
        )

        exchange.assert_not_awaited()


def test_callback_rejects_wrong_nonce(
    isolated_auth_db,
    google_settings,
):
    with (
        patch.object(
            auth,
            "_exchange_code",
            new_callable=AsyncMock,
            return_value={
                "id_token": "mock-id-token"
            },
        ),
        patch.object(
            auth,
            "_verify_google_id_token",
            return_value={
                "sub": "google-user",
                "email": "person@example.com",
                "email_verified": True,
                "name": "Person",
                "nonce": "wrong-nonce",
            },
        ),
        TestClient(app) as client,
    ):
        _, query = begin_login(
            client
        )

        state = query["state"][0]

        response = client.get(
            (
                "/api/v1/auth/google/callback"
                f"?code=code"
                f"&state={state}"
            ),
            follow_redirects=False,
        )

        assert response.status_code == 401
        assert (
            response.json()["detail"]["code"]
            == "invalid_google_nonce"
        )


def test_unverified_google_email_is_rejected(
    isolated_auth_db,
    google_settings,
):
    with (
        patch.object(
            auth,
            "_exchange_code",
            new_callable=AsyncMock,
            return_value={
                "id_token": "mock-id-token"
            },
        ),
        patch.object(
            auth,
            "_verify_google_id_token",
        ) as verify,
        TestClient(app) as client,
    ):
        _, query = begin_login(
            client
        )

        state = query["state"][0]
        nonce = query["nonce"][0]

        verify.return_value = {
            "sub": "google-user",
            "email": "person@example.com",
            "email_verified": False,
            "name": "Person",
            "nonce": nonce,
        }

        response = client.get(
            (
                "/api/v1/auth/google/callback"
                f"?code=code"
                f"&state={state}"
            ),
            follow_redirects=False,
        )

        assert response.status_code == 401

        assert (
            response.json()["detail"]["code"]
            == "google_identity_incomplete"
        )


def test_me_requires_session(
    isolated_auth_db,
    google_settings,
):
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/auth/me"
        )

    assert response.status_code == 401
    assert (
        response.json()["detail"]["code"]
        == "not_authenticated"
    )
