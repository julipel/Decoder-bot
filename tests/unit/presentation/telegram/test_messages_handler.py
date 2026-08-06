"""
Тесты presentation/telegram/handlers/messages.py — без обращения к
реальному Telegram API. `ProcessUserMessage` собирается по-настоящему,
но поверх fake `LLMProvider` и in-memory fake-репозиториев (Sprint 2,
задача S2-06 — `ProcessUserMessage` теперь зависит от репозиториев, не
только от `LLMProvider`; см. `tests/support/fake_conversation_repositories.py`)
— так handler-тесты проверяют реальную цепочку
Update → Command → use case → ответ, не подменяя use case целиком.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from telegram import Update
from tests.support.fake_conversation_repositories import make_in_memory_repositories_factory
from tests.support.fake_knowledge_repositories import FakeKnowledgeSearchService
from tests.support.prompt_engine import make_test_prompt_builder

from dekoder.application.conversation.dto import LLMRequest, LLMResponse
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.presentation.telegram.handlers.messages import (
    UNEXPECTED_ERROR_MESSAGE,
    TextMessageHandler,
)
from dekoder.presentation.telegram.mapper import TELEGRAM_SAFE_MESSAGE_LIMIT
from dekoder.shared.errors import LLMProviderError


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


def _make_process_user_message(provider: FakeLLMProvider) -> ProcessUserMessage:
    return ProcessUserMessage(
        llm_provider=provider,
        repositories=make_in_memory_repositories_factory(),
        prompt_builder=make_test_prompt_builder(),
        knowledge_search=FakeKnowledgeSearchService(),
        default_model=ModelId("openai/gpt-4o-mini"),
        temperature=0.7,
        max_tokens=512,
        max_relevant_memory=5,
    )


def _make_response(text: str = "Здравствуйте!") -> LLMResponse:
    return LLMResponse(
        text=text,
        provider_id=ProviderId("openrouter"),
        model_id=ModelId("openai/gpt-4o-mini"),
        input_tokens=10,
        output_tokens=5,
        duration_ms=42.0,
    )


def _make_update(text: str = "Привет!", user_id: int = 12345) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.text = text
    update.effective_message.reply_text = AsyncMock()
    return update


class TestSuccessfulMessage:
    async def test_replies_with_generated_response(self) -> None:
        provider = FakeLLMProvider(response=_make_response("Здравствуйте!"))
        handler = TextMessageHandler(_make_process_user_message(provider))
        update = _make_update("Привет!")

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with("Здравствуйте!")

    async def test_sends_the_users_text_through_to_the_provider(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        handler = TextMessageHandler(_make_process_user_message(provider))

        await handler(_make_update(text="Как дела?"), MagicMock())

        assert provider.received_requests[0].messages[-1].content == "Как дела?"

    async def test_generates_a_fresh_correlation_id_per_call(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        handler = TextMessageHandler(_make_process_user_message(provider))

        await handler(_make_update(), MagicMock())
        await handler(_make_update(), MagicMock())

        first, second = provider.received_requests
        assert first.correlation_id != second.correlation_id

    async def test_splits_long_response_into_multiple_messages(self) -> None:
        long_text = "word " * (TELEGRAM_SAFE_MESSAGE_LIMIT // 4)
        provider = FakeLLMProvider(response=_make_response(long_text))
        handler = TextMessageHandler(_make_process_user_message(provider))
        update = _make_update()

        await handler(update, MagicMock())

        assert update.effective_message.reply_text.await_count > 1
        for call in update.effective_message.reply_text.await_args_list:
            assert len(call.args[0]) <= TELEGRAM_SAFE_MESSAGE_LIMIT


class TestIgnoresNonTextUpdates:
    async def test_ignores_update_without_message_text(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        handler = TextMessageHandler(_make_process_user_message(provider))
        update = _make_update()
        update.effective_message.text = None

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_not_awaited()
        assert provider.received_requests == []

    async def test_ignores_update_without_message(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        handler = TextMessageHandler(_make_process_user_message(provider))
        update = _make_update()
        update.effective_message = None

        await handler(update, MagicMock())

        assert provider.received_requests == []


class TestDekoderErrorHandling:
    async def test_empty_text_shows_the_domain_safe_user_message(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        handler = TextMessageHandler(_make_process_user_message(provider))
        update = _make_update(text="   ")  # только пробелы -> ValidationError внутри execute()

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with("Сообщение не может быть пустым.")
        assert provider.received_requests == []

    async def test_llm_provider_error_shows_its_safe_user_message(self) -> None:
        safe_message = "Не удалось получить ответ от модели, попробуйте позже."
        provider = FakeLLMProvider(error=LLMProviderError(message="OpenRouter boom", user_message=safe_message))
        handler = TextMessageHandler(_make_process_user_message(provider))
        update = _make_update()

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(safe_message)


class TestUnexpectedErrorHandling:
    async def test_unexpected_exception_shows_neutral_message(self) -> None:
        provider = FakeLLMProvider(error=RuntimeError("secret=abc123, stack trace details"))
        handler = TextMessageHandler(_make_process_user_message(provider))
        update = _make_update()

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(UNEXPECTED_ERROR_MESSAGE)

    async def test_unexpected_exception_details_never_reach_the_user(self) -> None:
        provider = FakeLLMProvider(error=RuntimeError("secret=abc123, stack trace details"))
        handler = TextMessageHandler(_make_process_user_message(provider))
        update = _make_update()

        await handler(update, MagicMock())

        sent_text = update.effective_message.reply_text.call_args.args[0]
        assert "secret=abc123" not in sent_text
        assert "RuntimeError" not in sent_text
        assert "Traceback" not in sent_text
