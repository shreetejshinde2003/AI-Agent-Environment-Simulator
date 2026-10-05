"""Phase 4.5.5C.2 tenant-scoped upload API tests."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import uploads as upload_routes


def test_upload_route_binds_selected_workspace_and_actor(monkeypatch):
    calls = {}

    monkeypatch.setattr(
        upload_routes,
        "require_request_permission",
        lambda request, workspace_id, permission: {"id": workspace_id},
    )
    monkeypatch.setattr(
        upload_routes,
        "request_user_id",
        lambda request: "USR-a",
    )

    def save(upload, *, workspace_id, user_id):
        calls["workspace_id"] = workspace_id
        calls["user_id"] = user_id
        calls["filename"] = upload.filename

    monkeypatch.setattr(
        upload_routes.repository,
        "save_upload_for_tenant",
        save,
    )

    app = FastAPI()
    app.include_router(upload_routes.router)
    client = TestClient(app)

    response = client.post(
        "/uploads?filename=brief.txt",
        content=b"brief",
        headers={
            "Content-Type": "text/plain",
            "X-Workspace-Id": "WS-a",
        },
    )

    assert response.status_code == 201
    assert calls == {
        "workspace_id": "WS-a",
        "user_id": "USR-a",
        "filename": "brief.txt",
    }


def test_upload_get_is_scoped_to_selected_workspace(monkeypatch):
    calls = {}

    monkeypatch.setattr(
        upload_routes,
        "require_request_permission",
        lambda request, workspace_id, permission: {"id": workspace_id},
    )

    monkeypatch.setattr(
        upload_routes,
        "request_user_id",
        lambda request: "USR-b",
    )

    def get(upload_id, *, workspace_id, user_id):
        calls["upload_id"] = upload_id
        calls["workspace_id"] = workspace_id
        calls["user_id"] = user_id
        return None

    monkeypatch.setattr(
        upload_routes.repository,
        "get_upload_for_tenant",
        get,
    )

    app = FastAPI()
    app.include_router(upload_routes.router)
    client = TestClient(app)

    response = client.get(
        "/uploads/U-secret",
        headers={"X-Workspace-Id": "WS-b"},
    )

    assert response.status_code == 404
    assert calls == {
        "upload_id": "U-secret",
        "workspace_id": "WS-b",
        "user_id": "USR-b",
    }
