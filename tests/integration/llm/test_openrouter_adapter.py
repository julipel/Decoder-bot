"""
Тесты OpenRouterLLMAdapter — respx перехватывает HTTP на уровне транспорта
`httpx.AsyncClient`, реальный OpenRouter никогда не вызывается.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import respx

from dekoder.application.conversation.dto import LLMRequest
from dekoder.domain.conversation.value_objects import MessageText, ModelId
from dekoder.infrastructure.llm.openrouter_adapter import OpenRouterLLMAdapter
from dekoder.shared.domain.identifiers import CorrelationId
from dekoder.shared.errors import LLMProviderError

BASE_URL = "https://openrouter.ai/api/v1"
CHAT_COMPLETIONS_URL = f"{BASE_URL}/chat/completions"


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=BASE_URL) as http_client:
        yield http_client


def _make_request(model: str = "openai/gpt-4o-mini") -> LLMRequest:
    return LLMRequest(
        system_prompt="Ты — ассистент.",
        user_message=MessageText("Привет!"),
        model_id=ModelId(model),
        temperature=0.7,
        max_tokens=512,
        correlation_id=CorrelationId("corr-1"),
    )


def _success_payload(model: str = "openai/gpt-4o-mini") -> dict[str, Any]:
    return {
        "id": "gen-1",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Здравствуйте!"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


class TestSuccessfulGeneration:
    @respx.mock
    async def test_returns_llm_response_built_from_openrouter_payload(self, client: httpx.AsyncClient) -> None:
        route = respx.post(CHAT_COMPLETIONS_URL).mock(return_value=httpx.Response(200, json=_success_payload()))
        adapter = OpenRouterLLMAdapter(client=client, api_key="sk-test")

        response = await adapter.generate(_make_request())

        assert route.called
        assert response.text == "Здравствуйте!"
        assert response.provider_id.value == "openrouter"
        assert response.model_id.value == "openai/gpt-4o-mini"
        assert response.input_tokens == 10
        assert response.output_tokens == 5
        assert response.duration_ms >= 0

    @respx.mock
    async def test_sends_expected_body_and_bearer_header(self, client: httpx.AsyncClient) -> None:
        route = respx.post(CHAT_COMPLETIONS_URL).mock(return_value=httpx.Response(200, json=_success_payload()))
        adapter = OpenRouterLLMAdapter(client=client, api_key="sk-test-key")

        await adapter.generate(_make_request())

        sent = route.calls.last.request
        assert sent.headers["Authorization"] == "Bearer sk-test-key"
        body = json.loads(sent.content)
        assert body == {
            "model": "openai/gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Ты — ассистент."},
                {"role": "user", "content": "Привет!"},
            ],
            "temperature": 0.7,
            "max_tokens": 512,
        }

    @respx.mock
    async def test_adds_optional_headers_when_provided(self, client: httpx.AsyncClient) -> None:
        route = respx.post(CHAT_COMPLETIONS_URL).mock(return_value=httpx.Response(200, json=_success_payload()))
        adapter = OpenRouterLLMAdapter(
            client=client,
            api_key="sk-test",
            http_referer="https://example.com",
            x_title="Dekoder",
        )

        await adapter.generate(_make_request())

        sent = route.calls.last.request
        assert sent.headers["HTTP-Referer"] == "https://example.com"
        assert sent.headers["X-Title"] == "Dekoder"

    @respx.mock
    async def test_omits_optional_headers_when_not_provided(self, client: httpx.AsyncClient) -> None:
        route = respx.post(CHAT_COMPLETIONS_URL).mock(return_value=httpx.Response(200, json=_success_payload()))
        adapter = OpenRouterLLMAdapter(client=client, api_key="sk-test")

        await adapter.generate(_make_request())

        sent = route.calls.last.request
        assert "HTTP-Referer" not in sent.headers
        assert "X-Title" not in sent.headers

    @respx.mock
    async def test_falls_back_to_requested_model_when_response_omits_model(self, client: httpx.AsyncClient) -> None:
        payload = _success_payload()
        del payload["model"]
        respx.post(CHAT_COMPLETIONS_URL).mock(return_value=httpx.Response(200, json=payload))
        adapter = OpenRouterLLMAdapter(client=client, api_key="sk-test")

        response = await adapter.generate(_make_request(model="anthropic/claude-3-haiku"))

        assert response.model_id.value == "anthropic/claude-3-haiku"

    @respx.mock
    async def test_usage_defaults_to_zero_when_absent(self, client: httpx.AsyncClient) -> None:
        payload = _success_payload()
        del payload["usage"]
        respx.post(CHAT_COMPLETIONS_URL).mock(return_value=httpx.Response(200, json=payload))
        adapter = OpenRouterLLMAdapter(client=client, api_key="sk-test")

        response = await adapter.generate(_make_request())

        assert response.input_tokens == 0
        assert response.output_tokens == 0


class TestErrorScenarios:
    @respx.mock
    async def test_timeout_raises_llm_provider_error(self, client: httpx.AsyncClient) -> None:
        respx.post(CHAT_COMPLETIONS_URL).mock(side_effect=httpx.TimeoutException("timed out"))
        adapter = OpenRouterLLMAdapter(client=client, api_key="sk-test")

        with pytest.raises(LLMProviderError) as exc_info:
            await adapter.generate(_make_request())

        assert exc_info.value.code == "LLM_PROVIDER_TIMEOUT"

    @respx.mock
    async def test_network_error_raises_llm_provider_error(self, client: httpx.AsyncClient) -> None:
        respx.post(CHAT_COMPLETIONS_URL).mock(side_effect=httpx.ConnectError("connection refused"))
        adapter = OpenRouterLLMAdapter(client=client, api_key="sk-test")

        with pytest.raises(LLMProviderError) as exc_info:
            await adapter.generate(_make_request())

        assert exc_info.value.code == "LLM_PROVIDER_NETWORK_ERROR"

    @respx.mock
    async def test_unauthorized_raises_llm_provider_error(self, client: httpx.AsyncClient) -> None:
        respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(401, json={"error": {"message": "invalid api key"}})
        )
        adapter = OpenRouterLLMAdapter(client=client, api_key="sk-bad")

        with pytest.raises(LLMProviderError) as exc_info:
            await adapter.generate(_make_request())

        assert exc_info.value.code == "LLM_PROVIDER_UNAUTHORIZED"

    @respx.mock
    async def test_rate_limit_raises_llm_provider_error(self, client: httpx.AsyncClient) -> None:
        respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(429, json={"error": {"message": "rate limited"}})
        )
        adapter = OpenRouterLLMAdapter(client=client, api_key="sk-test")

        with pytest.raises(LLMProviderError) as exc_info:
            await adapter.generate(_make_request())

        assert exc_info.value.code == "LLM_PROVIDER_RATE_LIMITED"

    @respx.mock
    async def test_server_error_raises_llm_provider_error(self, client: httpx.AsyncClient) -> None:
        respx.post(CHAT_COMPLETIONS_URL).mock(return_value=httpx.Response(500, text="internal error"))
        adapter = OpenRouterLLMAdapter(client=client, api_key="sk-test")

        with pytest.raises(LLMProviderError) as exc_info:
            await adapter.generate(_make_request())

        assert exc_info.value.code == "LLM_PROVIDER_SERVER_ERROR"

    @respx.mock
    async def test_malformed_json_raises_llm_provider_error(self, client: httpx.AsyncClient) -> None:
        respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(200, content=b"not valid json", headers={"content-type": "application/json"})
        )
        adapter = OpenRouterLLMAdapter(client=client, api_key="sk-test")

        with pytest.raises(LLMProviderError) as exc_info:
            await adapter.generate(_make_request())

        assert exc_info.value.code == "LLM_PROVIDER_MALFORMED_RESPONSE"

    @respx.mock
    async def test_schema_mismatch_raises_llm_provider_error(self, client: httpx.AsyncClient) -> None:
        respx.post(CHAT_COMPLETIONS_URL).mock(return_value=httpx.Response(200, json={"choices": "not-a-list"}))
        adapter = OpenRouterLLMAdapter(client=client, api_key="sk-test")

        with pytest.raises(LLMProviderError) as exc_info:
            await adapter.generate(_make_request())

        assert exc_info.value.code == "LLM_PROVIDER_MALFORMED_RESPONSE"

    @respx.mock
    async def test_empty_choices_raises_llm_provider_error(self, client: httpx.AsyncClient) -> None:
        payload = _success_payload()
        payload["choices"] = []
        respx.post(CHAT_COMPLETIONS_URL).mock(return_value=httpx.Response(200, json=payload))
        adapter = OpenRouterLLMAdapter(client=client, api_key="sk-test")

        with pytest.raises(LLMProviderError) as exc_info:
            await adapter.generate(_make_request())

        assert exc_info.value.code == "LLM_PROVIDER_EMPTY_CHOICES"

    @respx.mock
    async def test_error_messages_never_contain_api_key(self, client: httpx.AsyncClient) -> None:
        respx.post(CHAT_COMPLETIONS_URL).mock(return_value=httpx.Response(401, json={"error": {"message": "invalid"}}))
        adapter = OpenRouterLLMAdapter(client=client, api_key="super-secret-key")

        with pytest.raises(LLMProviderError) as exc_info:
            await adapter.generate(_make_request())

        assert "super-secret-key" not in exc_info.value.message
        assert "super-secret-key" not in exc_info.value.user_message
        assert "super-secret-key" not in repr(exc_info.value)
