"""Previously global runtime statistics now use the same tenant/RBAC boundary."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.routes import agents, auth, simulation, workspaces
from app.main import app
from app.models.schemas import StageExecution
from app.security.session import create_opaque_token, session_expiry, token_digest
from app.storage.database import Repository
from test_tenant_repository_primitives import make_task, make_user


@pytest.fixture
def statistics_world(tmp_path, monkeypatch):
    repo = Repository(f"sqlite:///{tmp_path / 'statistics.db'}")
    repo.initialize()
    for module in (agents, auth, simulation, workspaces):
        monkeypatch.setattr(module, "repository", repo)
    for uid, tokens in (("USR-a", 7), ("USR-b", 999)):
        repo.save_user(make_user(uid))
        ws = repo.ensure_personal_workspace(uid)["id"]
        task = make_task(f"T-{uid}", ws)
        task.stages = [StageExecution(
            agent_id="direct", output_key="final_answer", status="completed",
            started_at=datetime.now(timezone.utc), total_tokens=tokens,
            output=f"private-{uid}", model=f"model-{uid}",
        )]
        repo.save(task)
    organization, _ = repo.create_organization(creator_user_id="USR-a", name="Statistics")
    org_task = make_task("T-org", organization["id"])
    org_task.stages = [StageExecution(agent_id="research", output_key="research_findings",
                                     status="active", started_at=datetime.now(timezone.utc))]
    repo.save(org_task)
    token = create_opaque_token()
    repo.save_auth_session({
        "id": "SES-a", "user_id": "USR-a", "token_digest": token_digest(token),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": session_expiry().isoformat(), "revoked_at": None,
    })
    monkeypatch.setattr(repo, "list", lambda: pytest.fail("unscoped statistics query"))
    client = TestClient(app)
    client.cookies.set("app_session", token)
    yield client, repo, organization
    client.close()
    repo.engine.dispose()


def test_runtime_statistics_do_not_expose_another_personal_workspace(statistics_world):
    client, _, _ = statistics_world
    for path in ("/api/v1/agents/stats", "/api/v1/agents/direct/stats"):
        response = client.get(path)
        assert response.status_code == 200
        records = response.json() if isinstance(response.json(), list) else [response.json()]
        direct = next(record for record in records if record["agentId"] == "direct")
        assert direct["callsMade"] == 1
        assert direct["totalTokensUsed"] == 7
        assert "USR-b" not in response.text
        assert direct["lastResponsePreview"] == "private-USR-a"


def test_roster_and_stats_respect_explicit_authorized_workspace(statistics_world):
    client, _, organization = statistics_world
    headers = {"X-Workspace-Id": organization["id"]}
    response = client.get("/api/v1/agents", headers=headers)
    assert response.status_code == 200
    research = next(row for row in response.json() if row["id"] == "research")
    assert research["status"] == "active"
    direct = client.get("/api/v1/agents/direct/stats", headers=headers).json()
    assert direct["callsMade"] == 0
    assert direct["lastResponsePreview"] is None
    assert client.get("/api/v1/agents/research", headers=headers).json()["status"] == "active"
    assert client.get("/api/v1/agents/stats", headers={"X-Workspace-Id": "WS-inaccessible"}).status_code == 404


@pytest.mark.parametrize("path", ["/api/v1/agents", "/api/v1/agents/stats", "/api/v1/agents/direct/stats"])
def test_tenant_derived_runtime_reads_require_authentication(statistics_world, path):
    client, _, _ = statistics_world
    client.cookies.clear()
    assert client.get(path).status_code == 401


def test_unavailable_controls_return_only_workspace_statistics_without_running_anything(statistics_world):
    client, _, _ = statistics_world
    response = client.post("/api/v1/simulation/pause")
    assert response.status_code == 200
    assert response.json()["supported"] is False
    assert response.json()["totalTasks"] == 1
    assert response.json()["totalTokens"] == 7
