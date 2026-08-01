"""
Тесты presentation/telegram/handlers/clear_conversation.py (Sprint 2,
задача S2-10) — без обращения к реальному Telegram API и без SQLAlchemy.
`ClearConversation` собирается по-настоящему, но поверх in-memory
fake-репозиториев (`tests/support/fake_conversation_repositories.py`, тот
же helper, что и тесты `TextMessageHandler`/`NewConversationHandler`) —
так handler-тесты проверяют реальную цепочку Update → Command → use case →
ответ, не подменяя use case целиком.
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from telegram import Update
from tests.support.fake_conversation_repositories import (
    FakeConversationRepository,
    FakeMessageRepository,
    FakeUserRepository,
    make_in_memory_repositories_factory,
)

from dekoder.application.conversation.dto import ClearConversationCommand, ClearConversationResult
from dekoder.application.conversation.use_cases.clear_conversation import ClearConversation
from dekoder.domain.conversation.entities import Message, MessageRole
from dekoder.presentation.telegram.handlers import clear_conversation as clear_conversation_module
from dekoder.presentation.telegram.handlers.clear_conversation import (
    CONVERSATION_ALREADY_EMPTY_MESSAGE,
    CONVERSATION_CLEARED_MESSAGE,
    NO_ACTIVE_CONVERSATION_MESSAGE,
    ClearConversationHandler,
)
from dekoder.shared.errors import ApplicationError


class RecordingClearConversation:
    """Spy, оборачивающий реальный use case, чтобы проверить переданные ему команды."""

    def __init__(self, use_case: ClearConversation) -> None:
        self._use_case = use_case
        self.received_commands: list[ClearConversationCommand] = []

    async def execute(self, command: ClearConversationCommand) -> ClearConversationResult:
        self.received_commands.append(command)
        return await self._use_case.execute(command)


def _make_use_case(
    users: FakeUserRepository | None = None,
    conversations: FakeConversationRepository | None = None,
    messages: FakeMessageRepository | None = None,
) -> RecordingClearConversation:
    users = users if users is not None else FakeUserRepository()
    conversations = conversations if conversations is not None else FakeConversationRepository()
    messages = messages if messages is not None else FakeMessageRepository()
    factory = make_in_memory_repositories_factory(users=users, conversations=conversations, messages=messages)
    return RecordingClearConversation(ClearConversation(repositories=factory))


def _make_update(user_id: int = 12345) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    return update


class TestUnknownUser:
    """Пользователь никогда не общался с ботом — нейтральное сообщение, не ошибка."""

    async def test_sends_no_active_conversation_message(self) -> None:
        use_case = _make_use_case()
        handler = ClearConversationHandler(use_case)
        update = _make_update(user_id=999)

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(NO_ACTIVE_CONVERSATION_MESSAGE)

    async def test_does_not_create_a_user(self) -> None:
        users = FakeUserRepository()
        use_case = _make_use_case(users=users)
        handler = ClearConversationHandler(use_case)

        await handler(_make_update(user_id=999), MagicMock())

        assert await users.get_by_telegram_user_id(999) is None


class TestUserWithoutActiveConversation:
    """Пользователь существует, но активного диалога нет — нейтральное сообщение, диалог не создаётся."""

    async def test_sends_no_active_conversation_message(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(321)
        use_case = _make_use_case(users=users)
        handler = ClearConversationHandler(use_case)
        update = _make_update(user_id=user.telegram_user_id)

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(NO_ACTIVE_CONVERSATION_MESSAGE)

    async def test_does_not_create_a_conversation(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(321)
        conversations = FakeConversationRepository()
        use_case = _make_use_case(users=users, conversations=conversations)
        handler = ClearConversationHandler(use_case)

        await handler(_make_update(user_id=user.telegram_user_id), MagicMock())

        assert await conversations.get_active_by_user_id(user.id) is None


class TestActiveConversationWithHistory:
    """Активный диалог с историей — история удаляется, диалог остаётся активным."""

    async def test_replies_with_cleared_message(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(777)
        conversations = FakeConversationRepository()
        conversation = await conversations.get_or_create_active(user.id)
        messages = FakeMessageRepository()
        await messages.save(
            Message(
                id=uuid4(),
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="Привет",
                created_at=datetime.now(UTC),
            )
        )
        use_case = _make_use_case(users=users, conversations=conversations, messages=messages)
        handler = ClearConversationHandler(use_case)
        update = _make_update(user_id=user.telegram_user_id)

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(CONVERSATION_CLEARED_MESSAGE)

    async def test_clears_the_history_and_keeps_the_conversation_active(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(777)
        conversations = FakeConversationRepository()
        conversation = await conversations.get_or_create_active(user.id)
        messages = FakeMessageRepository()
        await messages.save(
            Message(
                id=uuid4(),
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content="Привет",
                created_at=datetime.now(UTC),
            )
        )
        use_case = _make_use_case(users=users, conversations=conversations, messages=messages)
        handler = ClearConversationHandler(use_case)

        await handler(_make_update(user_id=user.telegram_user_id), MagicMock())

        assert await messages.history(conversation.id) == []
        still_active = await conversations.get_active_by_user_id(user.id)
        assert still_active is not None
        assert still_active.id == conversation.id
        assert still_active.is_active


class TestActiveConversationAlreadyEmpty:
    """Активный диалог без сообщений — идемпотентный исход, отдельное сообщение."""

    async def test_replies_with_already_empty_message(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(888)
        conversations = FakeConversationRepository()
        await conversations.get_or_create_active(user.id)
        use_case = _make_use_case(users=users, conversations=conversations)
        handler = ClearConversationHandler(use_case)
        update = _make_update(user_id=user.telegram_user_id)

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(CONVERSATION_ALREADY_EMPTY_MESSAGE)


class TestCallsUseCaseWithCorrectArguments:
    async def test_passes_telegram_user_id_from_update(self) -> None:
        use_case = _make_use_case()
        handler = ClearConversationHandler(use_case)

        await handler(_make_update(user_id=54321), MagicMock())

        assert len(use_case.received_commands) == 1
        assert use_case.received_commands[0] == ClearConversationCommand(telegram_user_id=54321)

    async def test_calls_the_use_case_exactly_once(self) -> None:
        use_case = _make_use_case()
        handler = ClearConversationHandler(use_case)

        await handler(_make_update(), MagicMock())

        assert len(use_case.received_commands) == 1


class TestIgnoresUpdatesWithoutMessage:
    async def test_ignores_update_without_message(self) -> None:
        use_case = _make_use_case()
        handler = ClearConversationHandler(use_case)
        update = _make_update()
        update.effective_message = None

        await handler(update, MagicMock())

        assert use_case.received_commands == []


class FakeFailingClearConversation:
    """Fake use case, поднимающий заданное исключение — без наследования от ClearConversation."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def execute(self, command: ClearConversationCommand) -> ClearConversationResult:
        raise self._error


class TestDekoderErrorHandling:
    async def test_shows_the_errors_safe_user_message(self) -> None:
        safe_message = "Не удалось очистить историю, попробуйте позже."
        use_case = FakeFailingClearConversation(ApplicationError(message="boom", user_message=safe_message))
        handler = ClearConversationHandler(use_case)
        update = _make_update()

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(safe_message)


class TestUnexpectedErrorHandling:
    async def test_unexpected_exception_shows_neutral_message(self) -> None:
        use_case = FakeFailingClearConversation(RuntimeError("secret=abc123, stack trace details"))
        handler = ClearConversationHandler(use_case)
        update = _make_update()

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(clear_conversation_module.UNEXPECTED_ERROR_MESSAGE)

    async def test_unexpected_exception_details_never_reach_the_user(self) -> None:
        use_case = FakeFailingClearConversation(RuntimeError("secret=abc123, stack trace details"))
        handler = ClearConversationHandler(use_case)
        update = _make_update()

        await handler(update, MagicMock())

        sent_text = update.effective_message.reply_text.call_args.args[0]
        assert "secret=abc123" not in sent_text
        assert "RuntimeError" not in sent_text
        assert "Traceback" not in sent_text


def _imported_module_names(module: object) -> set[str]:
    """
    Разбирает исходный файл модуля через `ast` и возвращает полные имена
    всех реально импортированных модулей (`import ...` / `from ... import`).
    Работает через AST, а не через поиск подстроки в тексте файла — тот же
    подход, что и в `test_new_conversation_handler.py`.
    """
    source_path = Path(inspect.getfile(module))
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


class TestNoDirectRepositoryOrOrmAccess:
    """
    Архитектурная проверка (backlog_2.md §15, инварианты 4/11/12;
    backlog_2_tasks.md S2-10): Telegram Adapter не импортирует SQLAlchemy,
    ORM-модели или конкретные реализации репозиториев напрямую — только
    use case, полученный через конструктор.
    """

    def test_clear_conversation_handler_module_does_not_import_sqlalchemy_or_repositories(self) -> None:
        imports = _imported_module_names(clear_conversation_module)

        assert not any(name.startswith("sqlalchemy") for name in imports)
        assert not any(name.startswith("dekoder.infrastructure") for name in imports)
