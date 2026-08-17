"""Тесты контракта LLMProvider (application/conversation/ports.py)."""

from __future__ import annotations

from dekoder.application.conversation.dto import LLMMessage, LLMRequest, LLMResponse
from dekoder.application.conversation.ports import LLMProvider
from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.shared.domain.identifiers import CorrelationId


class FakeLLMProvider:
    """Fake без наследования от LLMProvider — Protocol допускает структурную типизацию."""

    def __init__(self, response: LLMResponse) -> None:
        self._response = response
        self.received_requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.received_requests.append(request)
        return self._response


def _make_request() -> LLMRequest:
    return LLMRequest(
        system_prompt="Ты — ассистент.",
        messages=[LLMMessage(role="user", content="Привет!")],
        model_id=ModelId("openai/gpt-4o-mini"),
        temperature=0.7,
        max_tokens=512,
        correlation_id=CorrelationId("corr-1"),
    )


def _make_response() -> LLMResponse:
    return LLMResponse(
        text="Здравствуйте!",
        provider_id=ProviderId("test-provider"),
        model_id=ModelId("openai/gpt-4o-mini"),
        input_tokens=10,
        output_tokens=5,
        duration_ms=42.0,
    )


class TestLLMProviderPortIsFakeable:
    def test_fake_satisfies_the_protocol_structurally(self) -> None:
        fake = FakeLLMProvider(_make_response())

        assert isinstance(fake, LLMProvider)

    async def test_fake_can_be_used_wherever_llm_provider_is_expected(self) -> None:
        expected_response = _make_response()
        fake: LLMProvider = FakeLLMProvider(expected_response)

        result = await fake.generate(_make_request())

        assert result == expected_response

    async def test_fake_records_the_request_it_received(self) -> None:
        fake = FakeLLMProvider(_make_response())
        request = _make_request()

        await fake.generate(request)

        assert fake.received_requests == [request]
