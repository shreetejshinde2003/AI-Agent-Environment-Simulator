"""Exercise real system agents/adapter with only the SDK request mocked."""
import asyncio
import json
from unittest.mock import AsyncMock

import httpx
from groq import APIStatusError

from app.agents.direct_agent import DirectAgent
from app.api.routes import tasks
from app.models.schemas import TaskStatus
from test_graph_runtime import runtime_world, new_task


def test_system_provider_error_does_not_persist_sdk_payload(runtime_world, monkeypatch):
    repo, agents, _, _ = runtime_world
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(400, request=request)
    error = APIStatusError("Provider diagnostic password=private-test-credential internal-host=private-host",
                           response=response, body={"debug": "private-test-credential"})
    adapter = AsyncMock(side_effect=error)
    monkeypatch.setattr("app.agents.llm_client._client.chat.completions.create", adapter)
    agents["direct"] = DirectAgent()
    task = new_task("single")
    repo.save(task)
    asyncio.run(tasks._run_task_inner(task.id, task=task))
    stored = repo.get(task.id)
    assert stored.status == TaskStatus.FAILED and stored.output is None
    assert stored.stages[0].status == "failed"
    evidence = json.dumps(stored.model_dump(mode="json"))
    assert "private-test-credential" not in evidence
    assert "private-host" not in evidence
    assert "provider request failed" in stored.error.lower()
    adapter.assert_awaited_once()
