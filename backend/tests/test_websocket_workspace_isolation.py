"""Phase 4.2.10 WebSocket tenant-boundary verification."""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.security.session import create_opaque_token, session_expiry, token_digest
from app.storage.database import repository
from app.websocket.manager import ConnectionManager, manager


def stamp():
    return datetime.now(timezone.utc).isoformat()


def make_user(user_id: str):
    now = stamp()
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


def add_session(client: TestClient, user_id: str):
    token = create_opaque_token()
    repository.save_auth_session(
        {
            "id": f"SES-{user_id}",
            "user_id": user_id,
            "token_digest": token_digest(token),
            "created_at": stamp(),
            "expires_at": session_expiry().isoformat(),
            "revoked_at": None,
        }
    )
    client.cookies.set("app_session", token)


@pytest.fixture
def isolated_repo():
    temp = tempfile.TemporaryDirectory()
    path = str(Path(temp.name) / "ws-tenancy.db")
    old_path = repository.path
    old_engine = repository._engine
    old_engine_url = repository._engine_url
    old_connections = dict(manager._active_connections)

    repository.path = path
    repository._engine = None
    repository._engine_url = None
    repository.initialize()
    manager._active_connections.clear()
    yield

    manager._active_connections.clear()
    manager._active_connections.update(old_connections)
    if repository._engine is not None:
        repository._engine.dispose()
    repository.path = old_path
    repository._engine = old_engine
    repository._engine_url = old_engine_url
    temp.cleanup()


class FakeSocket:
    def __init__(self):
        self.messages = []

    async def accept(self):
        return None

    async def send_text(self, message):
        self.messages.append(message)


def test_connection_manager_sends_tenant_event_only_to_matching_workspace():
    scoped = ConnectionManager()
    personal = FakeSocket()
    iict = FakeSocket()
    asyncio.run(scoped.connect(personal, "WS-personal"))
    asyncio.run(scoped.connect(iict, "WS-iict"))

    asyncio.run(
        scoped.broadcast(
            "task_updated",
            {"simulationId": "T-iict"},
            workspace_id="WS-iict",
        )
    )

    assert personal.messages == []
    assert len(iict.messages) == 1
    assert "T-iict" in iict.messages[0]


def test_websocket_requires_authenticated_session(isolated_repo):
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws/live?workspaceId=WS-missing"):
                pass
        assert exc.value.code == 4401


def test_websocket_rejects_workspace_without_membership(isolated_repo):
    owner = make_user("USR-owner")
    outsider = make_user("USR-outsider")
    repository.save_user(owner)
    repository.save_user(outsider)
    organization, _ = repository.create_organization(
        creator_user_id=owner["id"],
        name="IICT",
    )

    with TestClient(app) as client:
        add_session(client, outsider["id"])
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                f"/ws/live?workspaceId={organization['id']}"
            ):
                pass
        assert exc.value.code == 4404


def test_websocket_binds_connection_to_resolved_workspace(isolated_repo):
    user = make_user("USR-owner")
    repository.save_user(user)
    organization, _ = repository.create_organization(
        creator_user_id=user["id"],
        name="IICT",
    )

    with TestClient(app) as client:
        add_session(client, user["id"])
        with client.websocket_connect(
            f"/ws/live?workspaceId={organization['id']}"
        ):
            assert organization["id"] in manager._active_connections.values()

    assert manager.connection_count == 0
