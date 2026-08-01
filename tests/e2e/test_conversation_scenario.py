"""
Сквозной тест первого вертикального среза (S1-15):

    Fake Telegram Update
            v
    Telegram Handler
            v
    ProcessUserMessage
            v
    Fake LLMProvider
            v
    Telegram Reply

Единственная подмена во всей цепочке — `FakeLLMProvider` (никакого
реального OpenRouter/Telegram API). Всё остальное — реальный код:
`presentation.telegram.bot.build_telegram_application` собирает
настоящий `telegram.ext.Application` с настоящими `CommandHandler`/
`MessageHandler`, а обработчики получают настоящий `ProcessUserMessage`.

Update — `MagicMock(spec=Update)` с минимально нужными атрибутами.
Хендлеры вызываются напрямую через уже зарегистрированные в
`application.handlers` объекты, а не через `Application.process_update()`:
последний требует `Application.initialize()`, который обращается к
Telegram `getMe` по сети, — то, чего этот тест обязан избежать
(«не обращайся к реальному Telegram API»). Само сопоставление
`CommandHandler`/`MessageHandler` по фильтрам — код python-telegram-bot,
не наш, и уже проверено библиотекой; здесь под проверкой — что
`build_telegram_application` регистрирует нужные хендлеры с нужным DI,
и что цепочка `Handler -> ProcessUserMessage -> LLMProvider -> ответ`
работает целиком.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler
from tests.support.fake_conversation_repositories import (
    FakeConversationRepository,
    FakeMessageRepository,
    FakeUserRepository,
    make_in_memory_repositories_factory,
)

from dekoder.application.conversation.dto import (
    LLMRequest,
    LLMResponse,
    ProcessUserMessageCommand,
    ProcessUserMessageResult,
)
from dekoder.application.conversation.use_cases.clear_conversation import ClearConversation
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.presentation.telegram.bot import (
    build_telegram_application,
    register_clear_conversation_handler,
    register_message_handler,
)
from dekoder.presentation.telegram.handlers.messages import UNEXPECTED_ERROR_MESSAGE
from dekoder.presentation.telegram.handlers.start import START_MESSAGE
from dekoder.presentation.telegram.mapper import TELEGRAM_SAFE_MESSAGE_LIMIT
from dekoder.shared.errors import LLMProviderError

_TEST_BOT_TOKEN = "123456:test-token"  # noqa: S105 - фиктивный токен для теста, не секрет


class FakeLLMProvider:
    """Единственная подмена во всей цепочке — реальный OpenRouterLLMAdapter сюда не подключается."""

    def __init__(self, response: LLMResponse | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.call_count = 0
        self.received_requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.call_count += 1
        self.received_requests.append(request)
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


def _make_process_user_message(provider: FakeLLMProvider) -> ProcessUserMessage:
    return ProcessUserMessage(
        llm_provider=provider,
        repositories=make_in_memory_repositories_factory(),
        default_model=ModelId("openai/gpt-4o-mini"),
        system_prompt="Ты — ассистент.",
        temperature=0.7,
        max_tokens=512,
    )


def _build_application(process_user_message: ProcessUserMessage) -> Application:
    application = build_telegram_application(bot_token=_TEST_BOT_TOKEN)
    register_message_handler(application, process_user_message)
    return application


def _handlers(application: Application) -> tuple[object, object]:
    """Достаёт callback'и уже зарегистрированных хендлеров — без обращения к сети."""
    registered = application.handlers[0]
    command_handler = next(h for h in registered if isinstance(h, CommandHandler))
    message_handler = next(h for h in registered if isinstance(h, MessageHandler))
    return command_handler.callback, message_handler.callback


def _make_update(text: str | None = "Привет!", user_id: int = 12345) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.text = text
    update.effective_message.reply_text = AsyncMock()
    return update


def _response(text: str = "Здравствуйте!") -> LLMResponse:
    return LLMResponse(
        text=text,
        provider_id=ProviderId("openrouter"),
        model_id=ModelId("openai/gpt-4o-mini"),
        input_tokens=10,
        output_tokens=5,
        duration_ms=42.0,
    )


class TestStartCommand:
    async def test_start_replies_with_greeting_without_calling_the_provider(self) -> None:
        provider = FakeLLMProvider(response=_response())
        application = _build_application(_make_process_user_message(provider))
        start_callback, _ = _handlers(application)
        update = _make_update()

        await start_callback(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(START_MESSAGE)
        assert provider.call_count == 0


class TestFullConversationScenario:
    async def test_extracts_text_user_id_and_correlation_id_calls_use_case_once_and_replies(
        self,
    ) -> None:
        provider = FakeLLMProvider(response=_response("Здравствуйте!"))
        process_user_message = _make_process_user_message(provider)

        captured_commands: list[ProcessUserMessageCommand] = []
        original_execute = process_user_message.execute

        async def _spy_execute(command: ProcessUserMessageCommand) -> ProcessUserMessageResult:
            captured_commands.append(command)
            return await original_execute(command)

        process_user_message.execute = _spy_execute  # type: ignore[method-assign]

        application = _build_application(process_user_message)
        _, message_callback = _handlers(application)
        update = _make_update(text="Как дела?", user_id=999)

        await message_callback(update, MagicMock())

        # текст извлекается
        assert provider.received_requests[0].messages[-1].content == "Как дела?"
        # user id передаётся
        assert captured_commands[0].telegram_user_id == 999
        # correlation id создаётся
        assert captured_commands[0].correlation_id
        # use case вызывается один раз
        assert len(captured_commands) == 1
        assert provider.call_count == 1
        # ответ отправляется
        update.effective_message.reply_text.assert_awaited_once_with("Здравствуйте!")

    async def test_correlation_id_is_fresh_per_message(self) -> None:
        provider = FakeLLMProvider(response=_response())
        application = _build_application(_make_process_user_message(provider))
        _, message_callback = _handlers(application)

        await message_callback(_make_update(), MagicMock())
        await message_callback(_make_update(), MagicMock())

        first, second = provider.received_requests
        assert first.correlation_id != second.correlation_id

    async def test_long_response_is_split_into_multiple_replies(self) -> None:
        long_text = "word " * (TELEGRAM_SAFE_MESSAGE_LIMIT // 4)
        provider = FakeLLMProvider(response=_response(long_text))
        application = _build_application(_make_process_user_message(provider))
        _, message_callback = _handlers(application)
        update = _make_update()

        await message_callback(update, MagicMock())

        assert update.effective_message.reply_text.await_count > 1
        for call in update.effective_message.reply_text.await_args_list:
            assert len(call.args[0]) <= TELEGRAM_SAFE_MESSAGE_LIMIT

    async def test_provider_error_is_translated_to_its_safe_user_message(self) -> None:
        safe_message = "Не удалось получить ответ от модели, попробуйте позже."
        provider = FakeLLMProvider(error=LLMProviderError(message="OpenRouter boom", user_message=safe_message))
        application = _build_application(_make_process_user_message(provider))
        _, message_callback = _handlers(application)
        update = _make_update()

        await message_callback(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(safe_message)

    async def test_unexpected_error_is_translated_to_a_neutral_message(self) -> None:
        provider = FakeLLMProvider(error=RuntimeError("secret=abc123, internal details"))
        application = _build_application(_make_process_user_message(provider))
        _, message_callback = _handlers(application)
        update = _make_update()

        await message_callback(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(UNEXPECTED_ERROR_MESSAGE)
        sent_text = update.effective_message.reply_text.call_args.args[0]
        assert "secret=abc123" not in sent_text

    async def test_empty_text_is_handled_correctly_without_calling_the_provider(self) -> None:
        provider = FakeLLMProvider(response=_response())
        application = _build_application(_make_process_user_message(provider))
        _, message_callback = _handlers(application)
        update = _make_update(text="   ")

        await message_callback(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with("Сообщение не может быть пустым.")
        assert provider.call_count == 0

    async def test_missing_text_is_ignored_correctly_without_calling_the_provider(self) -> None:
        provider = FakeLLMProvider(response=_response())
        application = _build_application(_make_process_user_message(provider))
        _, message_callback = _handlers(application)
        update = _make_update(text=None)

        await message_callback(update, MagicMock())

        update.effective_message.reply_text.assert_not_awaited()
        assert provider.call_count == 0


class TestClearCommandRouting:
    """
    Sprint 2, задача S2-10: `/clear` — маршрутизация через реальный
    `telegram.ext.Application` (тот же подход, что и остальной этот файл —
    без сети, без реального Telegram API). `ProcessUserMessage` и
    `ClearConversation` собираются поверх ОДНИХ И ТЕХ ЖЕ in-memory
    fake-репозиториев, чтобы проверить, что `/clear` работает над тем же
    диалогом, что и обычные сообщения.
    """

    def _build(
        self, provider: FakeLLMProvider
    ) -> tuple[object, object, object, FakeUserRepository, FakeConversationRepository, FakeMessageRepository]:
        users = FakeUserRepository()
        conversations = FakeConversationRepository()
        messages = FakeMessageRepository()
        factory = make_in_memory_repositories_factory(users=users, conversations=conversations, messages=messages)
        process_user_message = ProcessUserMessage(
            llm_provider=provider,
            repositories=factory,
            default_model=ModelId("openai/gpt-4o-mini"),
            system_prompt="Ты — ассистент.",
            temperature=0.7,
            max_tokens=512,
        )
        clear_conversation = ClearConversation(repositories=factory)

        application = build_telegram_application(bot_token=_TEST_BOT_TOKEN)
        register_message_handler(application, process_user_message)
        register_clear_conversation_handler(application, clear_conversation)

        registered = application.handlers[0]
        message_handler = next(h for h in registered if isinstance(h, MessageHandler))
        clear_handler = next(h for h in registered if isinstance(h, CommandHandler) and "clear" in h.commands)
        return message_handler.callback, clear_handler.callback, application, users, conversations, messages

    async def test_clear_is_registered_as_its_own_command_handler_not_the_message_handler(self) -> None:
        provider = FakeLLMProvider(response=_response())
        message_callback, clear_callback, _, _, _, _ = self._build(provider)

        assert clear_callback is not message_callback

    async def test_calling_the_clear_handler_does_not_invoke_the_llm_provider(self) -> None:
        # `/clear` доходит только до `ClearConversation` — маршрутизация
        # `CommandHandler("clear", ...)` vs `MessageHandler(filters.TEXT &
        # ~filters.COMMAND, ...)` — код python-telegram-bot, уже проверенный
        # библиотекой (см. докстринг модуля); здесь под проверкой то, что
        # НАШ обработчик `/clear` не касается `ProcessUserMessage`/`LLMProvider`.
        provider = FakeLLMProvider(response=_response())
        _, clear_callback, _, _, _, _ = self._build(provider)

        await clear_callback(_make_update(text="/clear", user_id=42), MagicMock())

        assert provider.call_count == 0

    async def test_clear_deletes_history_but_keeps_the_same_conversation_active(self) -> None:
        provider = FakeLLMProvider(response=_response("Здравствуйте!"))
        message_callback, clear_callback, _, users, conversations, messages = self._build(provider)

        await message_callback(_make_update(text="Привет!", user_id=42), MagicMock())

        user = await users.get_by_telegram_user_id(42)
        assert user is not None
        conversation_before = await conversations.get_active_by_user_id(user.id)
        assert conversation_before is not None
        assert len(await messages.history(conversation_before.id)) == 2  # user + assistant

        await clear_callback(_make_update(text="/clear", user_id=42), MagicMock())

        assert await messages.history(conversation_before.id) == []
        conversation_after_clear = await conversations.get_active_by_user_id(user.id)
        assert conversation_after_clear is not None
        assert conversation_after_clear.id == conversation_before.id

    async def test_a_normal_message_after_clear_continues_in_the_same_conversation(self) -> None:
        provider = FakeLLMProvider(response=_response("Здравствуйте!"))
        message_callback, clear_callback, _, users, conversations, _ = self._build(provider)

        await message_callback(_make_update(text="Привет!", user_id=42), MagicMock())
        user = await users.get_by_telegram_user_id(42)
        assert user is not None
        conversation_before = await conversations.get_active_by_user_id(user.id)
        assert conversation_before is not None

        await clear_callback(_make_update(text="/clear", user_id=42), MagicMock())
        await message_callback(_make_update(text="Как дела?", user_id=42), MagicMock())

        conversation_after = await conversations.get_active_by_user_id(user.id)
        assert conversation_after is not None
        assert conversation_after.id == conversation_before.id
