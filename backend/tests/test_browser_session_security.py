"""Cookie browser boundaries and continued authorization on live connections."""
from functools import partial
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.storage.database import repository
from app.storage import models as dbm
from app.websocket.manager import manager
from test_websocket_workspace_isolation import isolated_repo, make_user, add_session


@pytest.mark.parametrize("origin", ["https://attacker.example", "null", "http://localhost:5173.attacker.example"])
def test_untrusted_browser_cannot_upload_with_session_cookie(isolated_repo, origin):
    repository.save_user(make_user("USR-owner"))
    with TestClient(app) as client:
        add_session(client, "USR-owner")
        response = client.post("/api/v1/uploads?filename=attack.txt", content="Injected reference",
                               headers={"Origin": origin, "Content-Type": "text/plain"})
        assert response.status_code == 403
        with repository.engine.connect() as connection:
            assert connection.execute(select(dbm.uploads)).all() == []


def test_untrusted_browser_cannot_force_logout(isolated_repo):
    repository.save_user(make_user("USR-owner"))
    with TestClient(app) as client:
        add_session(client, "USR-owner")
        assert client.post("/api/v1/auth/logout", headers={"Origin": "https://attacker.example"}).status_code == 403
        assert client.get("/api/v1/auth/me").status_code == 200


def test_allowed_browser_upload_and_logout_remain_functional(isolated_repo):
    repository.save_user(make_user("USR-owner"))
    with TestClient(app) as client:
        add_session(client, "USR-owner")
        headers = {"Origin": "http://localhost:5173", "Content-Type": "text/plain"}
        assert client.post("/api/v1/uploads?filename=allowed.txt", content="Reference", headers=headers).status_code == 201
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204


@pytest.mark.parametrize("headers", [
    {"Sec-Fetch-Site": "cross-site"},
    {"Sec-Fetch-Site": "same-site"},
    {"Referer": "https://attacker.example/form"},
    {"Referer": "http://localhost:5173.attacker.example/form"},
])
def test_browser_without_trusted_source_cannot_mutate(isolated_repo, headers):
    repository.save_user(make_user("USR-owner"))
    with TestClient(app) as client:
        add_session(client, "USR-owner")
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 403
        assert client.get("/api/v1/auth/me").status_code == 200


def test_trusted_referer_and_cors_preflight_remain_functional(isolated_repo):
    repository.save_user(make_user("USR-owner"))
    with TestClient(app) as client:
        add_session(client, "USR-owner")
        headers = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"}
        response = client.options("/api/v1/auth/logout", headers=headers)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert client.post("/api/v1/auth/logout", headers={"Referer": "http://localhost:5173/agents"}).status_code == 204


@pytest.mark.parametrize("origin", ["https://attacker.example", "null"])
def test_untrusted_browser_cannot_open_authenticated_websocket(isolated_repo, origin):
    repository.save_user(make_user("USR-owner"))
    with TestClient(app) as client:
        add_session(client, "USR-owner")
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("/ws/live", headers={"Origin": origin}):
                pass
        assert error.value.code == 4403


@pytest.mark.parametrize("revocation", ["membership", "logout", "expiry", "user", "workspace"])
def test_existing_socket_stops_receiving_after_authority_removed(isolated_repo, revocation):
    repository.save_user(make_user("USR-owner"))
    repository.save_user(make_user("USR-member"))
    organization, code = repository.create_organization(creator_user_id="USR-owner", name="Live security")
    repository.join_organization(user_id="USR-member", join_code=code)
    workspace_id = organization["id"]
    with TestClient(app) as client:
        add_session(client, "USR-member")
        with client.websocket_connect(f"/ws/live?workspaceId={workspace_id}", headers={"Origin": "http://localhost:5173"}) as websocket:
            broadcast = partial(manager.broadcast, "task_updated", {"private": "workspace evidence"}, workspace_id=workspace_id)
            client.portal.call(broadcast)
            assert websocket.receive_json()["data"]["private"] == "workspace evidence"
            if revocation == "membership":
                repository.deactivate_organization_membership(workspace_id=workspace_id, target_user_id="USR-member", actor_user_id="USR-owner")
            elif revocation == "logout":
                assert client.post("/api/v1/auth/logout").status_code == 204
            elif revocation == "expiry":
                with repository.engine.begin() as connection:
                    connection.execute(update(dbm.auth_sessions).where(dbm.auth_sessions.c.id == "SES-USR-member").values(expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()))
            elif revocation == "user":
                repository.save_user(dict(make_user("USR-member"), active=False))
            else:
                workspace = repository.get_workspace(workspace_id)
                repository.save_workspace(dict(workspace, active=False))
            client.portal.call(broadcast)
            with pytest.raises(WebSocketDisconnect):
                websocket.receive_json()
    assert manager.connection_count == 0
