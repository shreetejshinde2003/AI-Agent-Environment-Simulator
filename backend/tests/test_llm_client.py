from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.llm_client import LLMResponse, call_llm


def test_llm_response_total_tokens_when_usage_is_measured():
    response = LLMResponse(
        text="Measured output",
        input_tokens=7,
        output_tokens=4,
        response_time_seconds=0.1,
        model="test-model",
    )

    assert response.total_tokens == 11


def test_llm_response_total_tokens_is_none_when_input_usage_missing():
    response = LLMResponse(
        text="Output",
        input_tokens=None,
        output_tokens=4,
        response_time_seconds=0.1,
        model="test-model",
    )

    assert response.total_tokens is None


def test_llm_response_total_tokens_is_none_when_output_usage_missing():
    response = LLMResponse(
        text="Output",
        input_tokens=7,
        output_tokens=None,
        response_time_seconds=0.1,
        model="test-model",
    )

    assert response.total_tokens is None


@pytest.mark.asyncio
async def test_call_llm_preserves_missing_provider_usage_as_none():
    provider_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="Provider output")
            )
        ],
        usage=None,
    )

    with patch(
        "app.agents.llm_client._client.chat.completions.create",
        new_callable=AsyncMock,
        return_value=provider_response,
    ) as create:
        response = await call_llm(
            prompt="Test prompt",
            model="test-model",
        )

    create.assert_awaited_once()

    assert response.text == "Provider output"
    assert response.model == "test-model"
    assert response.input_tokens is None
    assert response.output_tokens is None
    assert response.total_tokens is None


@pytest.mark.asyncio
async def test_call_llm_preserves_real_zero_usage():
    provider_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="Provider output")
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=0,
            completion_tokens=0,
        ),
    )

    with patch(
        "app.agents.llm_client._client.chat.completions.create",
        new_callable=AsyncMock,
        return_value=provider_response,
    ):
        response = await call_llm(
            prompt="Test prompt",
            model="test-model",
        )

    assert response.input_tokens == 0
    assert response.output_tokens == 0
    assert response.total_tokens == 0