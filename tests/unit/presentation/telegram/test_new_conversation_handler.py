"""
Тесты presentation/telegram/handlers/new_conversation.py (Sprint 2, задача
S2-08) — без обращения к реальному Telegram API и без SQLAlchemy.
`StartNewConversation` собирается по-настоящему, но поверх in-memory
fake-репозиториев (`tests/support/fake_conversation_repositories.py`, тот
же helper, что и тесты `TextMessageHandler`/`ProcessUserMessage`) — так
handler-тесты проверяют реальную цепочку Update → Command → use case →
ответ, не подменяя use case целиком.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from telegram import Update
from tests.support.fake_conversation_repositories import (
    FakeConversationRepository,
    FakeUserRepository,
    make_in_memory_repositories_factory,
)

from dekoder.application.conversation.dto import StartNewConversationCommand, StartNewConversationResult
from dekoder.application.conversation.use_cases.start_new_conversation import StartNewConversation
from dekoder.presentation.telegram import bot as bot_module
from dekoder.presentation.telegram.handlers import new_conversation as new_conversation_module
from dekoder.presentation.telegram.handlers.new_conversation import (
    NEW_CONVERSATION_STARTED_MESSAGE,
    NO_PREVIOUS_INTERACTION_MESSAGE,
    NewConversationHandler,
)
from dekoder.shared.errors import ApplicationError


class RecordingStartNewConversation:
    """Spy, оборачивающий реальный use case, чтобы проверить переданные ему команды."""

    def __init__(self, use_case: StartNewConversation) -> None:
        self._use_case = use_case
        self.received_commands: list[StartNewConversationCommand] = []

    async def execute(self, command: StartNewConversationCommand) -> StartNewConversationResult:
        self.received_commands.append(command)
        return await self._use_case.execute(command)


def _make_use_case(
    users: FakeUserRepository | None = None,
    conversations: FakeConversationRepository | None = None,
) -> RecordingStartNewConversation:
    users = users if users is not None else FakeUserRepository()
    conversations = conversations if conversations is not None else FakeConversationRepository()
    factory = make_in_memory_repositories_factory(users=users, conversations=conversations)
    return RecordingStartNewConversation(StartNewConversation(repositories=factory))


def _make_update(user_id: int = 12345) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    return update


class TestUnknownUser:
    """Пользователь никогда не общался с ботом — команда завершается штатно, без ошибки."""

    async def test_sends_no_previous_interaction_message(self) -> None:
        use_case = _make_use_case()
        handler = NewConversationHandler(use_case)
        update = _make_update(user_id=999)

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(NO_PREVIOUS_INTERACTION_MESSAGE)

    async def test_does_not_raise(self) -> None:
        use_case = _make_use_case()
        handler = NewConversationHandler(use_case)

        # Отсутствие исключения — сам факт успешного awaited-вызова ниже.
        await handler(_make_update(user_id=999), MagicMock())


class TestUserWithoutActiveConversation:
    """Пользователь существует, но активного диалога нет — создаётся новый, отправляется подтверждение."""

    async def test_replies_with_confirmation(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(321)
        use_case = _make_use_case(users=users)
        handler = NewConversationHandler(use_case)
        update = _make_update(user_id=user.telegram_user_id)

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(NEW_CONVERSATION_STARTED_MESSAGE)

    async def test_creates_new_active_conversation(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(321)
        conversations = FakeConversationRepository()
        use_case = _make_use_case(users=users, conversations=conversations)
        handler = NewConversationHandler(use_case)

        await handler(_make_update(user_id=user.telegram_user_id), MagicMock())

        active = await conversations.get_active_by_user_id(user.id)
        assert active is not None
        assert active.is_active


class TestUserWithActiveConversation:
    """Пользователь с активным диалогом — use case закрывает старый и создаёт новый, отправляется подтверждение."""

    async def test_replies_with_confirmation(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(777)
        conversations = FakeConversationRepository()
        await conversations.get_or_create_active(user.id)
        use_case = _make_use_case(users=users, conversations=conversations)
        handler = NewConversationHandler(use_case)
        update = _make_update(user_id=user.telegram_user_id)

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(NEW_CONVERSATION_STARTED_MESSAGE)

    async def test_closes_previous_conversation_and_creates_new_one(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(777)
        conversations = FakeConversationRepository()
        previous = await conversations.get_or_create_active(user.id)
        use_case = _make_use_case(users=users, conversations=conversations)
        handler = NewConversationHandler(use_case)

        await handler(_make_update(user_id=user.telegram_user_id), MagicMock())

        stored_previous = await conversations.get_by_id(previous.id)
        assert stored_previous is not None
        assert not stored_previous.is_active

        active = await conversations.get_active_by_user_id(user.id)
        assert active is not None
        assert active.id != previous.id


class TestCallsUseCaseWithCorrectArguments:
    async def test_passes_telegram_user_id_from_update(self) -> None:
        use_case = _make_use_case()
        handler = NewConversationHandler(use_case)

        await handler(_make_update(user_id=54321), MagicMock())

        assert len(use_case.received_commands) == 1
        assert use_case.received_commands[0] == StartNewConversationCommand(telegram_user_id=54321)


class TestIgnoresUpdatesWithoutMessage:
    async def test_ignores_update_without_message(self) -> None:
        use_case = _make_use_case()
        handler = NewConversationHandler(use_case)
        update = _make_update()
        update.effective_message = None

        await handler(update, MagicMock())

        assert use_case.received_commands == []


class FakeFailingStartNewConversation:
    """Fake use case, поднимающий заданное исключение — без наследования от StartNewConversation."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def execute(self, command: StartNewConversationCommand) -> StartNewConversationResult:
        raise self._error


class TestDekoderErrorHandling:
    async def test_shows_the_errors_safe_user_message(self) -> None:
        safe_message = "Не удалось начать новый диалог, попробуйте позже."
        use_case = FakeFailingStartNewConversation(ApplicationError(message="boom", user_message=safe_message))
        handler = NewConversationHandler(use_case)
        update = _make_update()

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(safe_message)


class TestUnexpectedErrorHandling:
    async def test_unexpected_exception_shows_neutral_message(self) -> None:
        use_case = FakeFailingStartNewConversation(RuntimeError("secret=abc123, stack trace details"))
        handler = NewConversationHandler(use_case)
        update = _make_update()

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(new_conversation_module.UNEXPECTED_ERROR_MESSAGE)

    async def test_unexpected_exception_details_never_reach_the_user(self) -> None:
        use_case = FakeFailingStartNewConversation(RuntimeError("secret=abc123, stack trace details"))
        handler = NewConversationHandler(use_case)
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
    Работает через AST, а не через поиск подстроки в тексте файла —
    поясняющие комментарии/docstrings модуля упоминают SQLAlchemy словами
    («не импортирует SQLAlchemy»), что дало бы ложное срабатывание при
    простом `"sqlalchemy" in source`.
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
    backlog_2_tasks.md S2-08): Telegram Adapter не импортирует SQLAlchemy,
    ORM-модели или конкретные реализации репозиториев напрямую — только
    use case, полученный через конструктор.
    """

    def test_new_conversation_handler_module_does_not_import_sqlalchemy_or_repositories(self) -> None:
        imports = _imported_module_names(new_conversation_module)

        assert not any(name.startswith("sqlalchemy") for name in imports)
        assert not any(name.startswith("dekoder.infrastructure") for name in imports)

    def test_bot_module_does_not_import_sqlalchemy_or_repositories(self) -> None:
        imports = _imported_module_names(bot_module)

        assert not any(name.startswith("sqlalchemy") for name in imports)
        assert not any(name.startswith("dekoder.infrastructure") for name in imports)
