"""Тесты ProcessUserMessage (application/conversation/use_cases/process_user_message.py)."""

from __future__ import annotations

import pytest

from dekoder.application.conversation.dto import (
    LLMRequest,
    LLMResponse,
    ProcessUserMessageCommand,
)
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.shared.domain.identifiers import CorrelationId
from dekoder.shared.errors import LLMProviderError, ValidationError


class FakeLLMProvider:
    """Fake без наследования от LLMProvider — Protocol допускает структурную типизацию."""

    def __init__(self, response: LLMResponse | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.received_requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.received_requests.append(request)
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


def _make_response(model_id: str = "openai/gpt-4o-mini") -> LLMResponse:
    return LLMResponse(
        text="Здравствуйте!",
        provider_id=ProviderId("openrouter"),
        model_id=ModelId(model_id),
        input_tokens=10,
        output_tokens=5,
        duration_ms=42.0,
    )


def _make_command(text: str = "Привет!", model_id: ModelId | None = None) -> ProcessUserMessageCommand:
    return ProcessUserMessageCommand(
        external_user_id="tg-123",
        message_text=text,
        correlation_id=CorrelationId("corr-1"),
        model_id=model_id,
    )


def _make_use_case(provider: FakeLLMProvider, default_model: str = "openai/gpt-4o-mini") -> ProcessUserMessage:
    return ProcessUserMessage(
        llm_provider=provider,
        default_model=ModelId(default_model),
        system_prompt="Ты — ассистент.",
        temperature=0.7,
        max_tokens=512,
    )


class TestSuccessfulScenario:
    async def test_returns_result_built_from_llm_response(self) -> None:
        response = _make_response()
        provider = FakeLLMProvider(response=response)
        use_case = _make_use_case(provider)

        result = await use_case.execute(_make_command())

        assert result.response_text == response.text
        assert result.provider_id == response.provider_id
        assert result.model_id == response.model_id
        assert result.duration_ms == response.duration_ms
        assert result.usage is not None
        assert result.usage.input_tokens == response.input_tokens
        assert result.usage.output_tokens == response.output_tokens

    async def test_builds_llm_request_from_command_and_constructor_settings(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case = _make_use_case(provider)
        command = _make_command(text="  Привет!  ")

        await use_case.execute(command)

        request = provider.received_requests[0]
        assert request.system_prompt == "Ты — ассистент."
        assert request.user_message.value == "Привет!"
        assert request.temperature == 0.7
        assert request.max_tokens == 512
        assert request.correlation_id == command.correlation_id


class TestEmptyText:
    async def test_empty_text_raises_validation_error(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case = _make_use_case(provider)

        with pytest.raises(ValidationError):
            await use_case.execute(_make_command(text=""))

    async def test_whitespace_only_text_raises_validation_error(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case = _make_use_case(provider)

        with pytest.raises(ValidationError):
            await use_case.execute(_make_command(text="   "))

    async def test_empty_text_does_not_call_provider(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case = _make_use_case(provider)

        with pytest.raises(ValidationError):
            await use_case.execute(_make_command(text=""))

        assert provider.received_requests == []


class TestModelResolution:
    async def test_uses_default_model_when_command_has_none(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case = _make_use_case(provider, default_model="openai/gpt-4o-mini")

        await use_case.execute(_make_command(model_id=None))

        assert provider.received_requests[0].model_id == ModelId("openai/gpt-4o-mini")

    async def test_uses_model_from_command_when_provided(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case = _make_use_case(provider, default_model="openai/gpt-4o-mini")

        await use_case.execute(_make_command(model_id=ModelId("anthropic/claude-3-haiku")))

        assert provider.received_requests[0].model_id == ModelId("anthropic/claude-3-haiku")


class TestProviderError:
    async def test_provider_error_propagates(self) -> None:
        error = LLMProviderError(
            message="OpenRouter timeout",
            user_message="Не удалось получить ответ от модели, попробуйте позже.",
        )
        provider = FakeLLMProvider(error=error)
        use_case = _make_use_case(provider)

        with pytest.raises(LLMProviderError) as exc_info:
            await use_case.execute(_make_command())

        assert exc_info.value is error
