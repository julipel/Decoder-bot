"""
Тесты presentation/telegram/handlers/web_search.py (внеспринтовая задача,
2026-09-09) — без обращения к реальному Telegram API и без SQLAlchemy.
`GetWebSearchStatus`/`SetWebSearchEnabled` собираются по-настоящему, но
поверх in-memory fake-репозиториев (`tests/support/
fake_conversation_repositories.py`) — тот же принцип, что и
`test_model_handler.py`.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from telegram import Update
from tests.support.fake_conversation_repositories import (
    FakeUserRepository,
    FakeWebSearchSettingRepository,
    make_in_memory_repositories_factory,
)

from dekoder.application.conversation.dto import GetWebSearchStatusCommand, GetWebSearchStatusResult
from dekoder.application.conversation.use_cases.get_web_search_status import GetWebSearchStatus
from dekoder.application.conversation.use_cases.set_web_search_enabled import SetWebSearchEnabled
from dekoder.presentation.telegram.handlers import web_search as web_search_module
from dekoder.presentation.telegram.handlers.web_search import (
    WEB_SEARCH_BUTTON_DISABLE,
    WEB_SEARCH_BUTTON_ENABLE,
    WebSearchCommandHandler,
    WebSearchToggleCallbackHandler,
)
from dekoder.shared.errors import ApplicationError


def _make_use_cases(
    users: FakeUserRepository | None = None,
    web_search: FakeWebSearchSettingRepository | None = None,
) -> tuple[GetWebSearchStatus, SetWebSearchEnabled, FakeUserRepository, FakeWebSearchSettingRepository]:
    users = users if users is not None else FakeUserRepository()
    web_search = web_search if web_search is not None else FakeWebSearchSettingRepository()
    factory = make_in_memory_repositories_factory(users=users, web_search=web_search)
    get_web_search_status = GetWebSearchStatus(repositories=factory)
    set_web_search_enabled = SetWebSearchEnabled(repositories=factory)
    return get_web_search_status, set_web_search_enabled, users, web_search


def _make_command_update(user_id: int = 12345) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    update.callback_query = None
    return update


def _make_callback_update(data: str, user_id: int = 12345) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_message = None
    query = MagicMock()
    query.data = data
    query.from_user = MagicMock(id=user_id)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    return update


class TestWebSearchCommandShowsCurrentStatus:
    async def test_shows_disabled_status_and_enable_button_for_new_user(self) -> None:
        get_web_search_status, _, _, _ = _make_use_cases()
        handler = WebSearchCommandHandler(get_web_search_status)
        update = _make_command_update(user_id=999)

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once()
        call_args = update.effective_message.reply_text.call_args
        assert "выключен" in call_args.args[0]
        keyboard = call_args.kwargs["reply_markup"]
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
        assert button_texts == [WEB_SEARCH_BUTTON_ENABLE]

    async def test_shows_enabled_status_and_disable_button_when_previously_enabled(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(123)
        web_search = FakeWebSearchSettingRepository({user.id: True})
        get_web_search_status, _, _, _ = _make_use_cases(users=users, web_search=web_search)
        handler = WebSearchCommandHandler(get_web_search_status)
        update = _make_command_update(user_id=123)

        await handler(update, MagicMock())

        call_args = update.effective_message.reply_text.call_args
        assert "включён" in call_args.args[0]
        keyboard = call_args.kwargs["reply_markup"]
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
        assert button_texts == [WEB_SEARCH_BUTTON_DISABLE]


class TestWebSearchToggleCallback:
    async def test_enables_and_confirms_with_disable_button(self) -> None:
        users = FakeUserRepository()
        await users.get_or_create_by_telegram_user_id(555)
        get_web_search_status, set_web_search_enabled, _, web_search = _make_use_cases(users=users)
        handler = WebSearchToggleCallbackHandler(set_web_search_enabled)
        update = _make_callback_update(data="websearch:on", user_id=555)

        await handler(update, MagicMock())

        update.callback_query.answer.assert_awaited_once_with()
        update.callback_query.edit_message_text.assert_awaited_once()
        call_args = update.callback_query.edit_message_text.call_args
        assert "включён" in call_args.args[0]
        keyboard = call_args.kwargs["reply_markup"]
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
        assert button_texts == [WEB_SEARCH_BUTTON_DISABLE]

        user = await users.get_by_telegram_user_id(555)
        assert user is not None
        assert await web_search.get_enabled(user.id) is True

    async def test_disables_and_confirms_with_enable_button(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(556)
        web_search = FakeWebSearchSettingRepository({user.id: True})
        _, set_web_search_enabled, _, _ = _make_use_cases(users=users, web_search=web_search)
        handler = WebSearchToggleCallbackHandler(set_web_search_enabled)
        update = _make_callback_update(data="websearch:off", user_id=556)

        await handler(update, MagicMock())

        call_args = update.callback_query.edit_message_text.call_args
        assert "выключен" in call_args.args[0]
        assert await web_search.get_enabled(user.id) is False


class TestCallbackUsesCallbackQueryFromUserNotEffectiveUser:
    async def test_toggle_is_attributed_to_the_callback_presser(self) -> None:
        users = FakeUserRepository()
        presser = await users.get_or_create_by_telegram_user_id(777)
        _, set_web_search_enabled, _, web_search = _make_use_cases(users=users)
        handler = WebSearchToggleCallbackHandler(set_web_search_enabled)
        update = _make_callback_update(data="websearch:on", user_id=777)
        # `effective_user`, будь он использован по ошибке, указывал бы на другого пользователя.
        update.effective_user = MagicMock(id=888)

        await handler(update, MagicMock())

        assert await web_search.get_enabled(presser.id) is True


class TestIgnoresUpdatesWithoutRelevantPayload:
    async def test_command_handler_ignores_update_without_message(self) -> None:
        get_web_search_status, _, _, _ = _make_use_cases()
        handler = WebSearchCommandHandler(get_web_search_status)
        update = _make_command_update()
        update.effective_message = None

        await handler(update, MagicMock())  # не должно бросить исключение

    async def test_callback_handler_ignores_update_without_callback_query(self) -> None:
        _, set_web_search_enabled, _, _ = _make_use_cases()
        handler = WebSearchToggleCallbackHandler(set_web_search_enabled)
        update = _make_command_update()
        update.callback_query = None

        await handler(update, MagicMock())  # не должно бросить исключение


class TestMalformedCallbackData:
    async def test_shows_unexpected_error_alert_when_data_does_not_match(self) -> None:
        _, set_web_search_enabled, _, _ = _make_use_cases()
        handler = WebSearchToggleCallbackHandler(set_web_search_enabled)
        update = _make_callback_update(data="not-a-web-search-callback")

        await handler(update, MagicMock())

        update.callback_query.answer.assert_awaited_once_with(
            web_search_module.UNEXPECTED_ERROR_MESSAGE, show_alert=True
        )
        update.callback_query.edit_message_text.assert_not_awaited()


class FakeFailingGetWebSearchStatus:
    """Fake use case, поднимающий заданное исключение — без наследования от GetWebSearchStatus."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def execute(self, command: GetWebSearchStatusCommand) -> GetWebSearchStatusResult:
        raise self._error


class TestDekoderErrorHandling:
    async def test_command_shows_the_errors_safe_user_message(self) -> None:
        safe_message = "Не удалось показать настройки, попробуйте позже."
        get_web_search_status = FakeFailingGetWebSearchStatus(
            ApplicationError(message="boom", user_message=safe_message)
        )
        handler = WebSearchCommandHandler(get_web_search_status)  # type: ignore[arg-type]
        update = _make_command_update()

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(safe_message)


class TestUnexpectedErrorHandling:
    async def test_command_shows_neutral_message(self) -> None:
        get_web_search_status = FakeFailingGetWebSearchStatus(RuntimeError("secret=abc123"))
        handler = WebSearchCommandHandler(get_web_search_status)  # type: ignore[arg-type]
        update = _make_command_update()

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(web_search_module.UNEXPECTED_ERROR_MESSAGE)


def _imported_module_names(module: object) -> set[str]:
    """Тот же способ, что и в test_model_handler.py — AST, не поиск подстроки в исходнике."""
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
    """Архитектурная проверка: presentation-слой не импортирует SQLAlchemy/ORM/репозитории напрямую."""

    def test_web_search_handler_module_does_not_import_sqlalchemy_or_repositories(self) -> None:
        imports = _imported_module_names(web_search_module)

        assert not any(name.startswith("sqlalchemy") for name in imports)
        assert not any(name.startswith("dekoder.infrastructure") for name in imports)


class TestCallbackPrefixDoesNotCollideWithOtherHandlers:
    """Callback-префикс `websearch:` не пересекается с `model:`/`profile:`/`memory_delete:`."""

    def test_web_search_callback_data_does_not_match_other_prefixes(self) -> None:
        for callback_data in ("websearch:on", "websearch:off"):
            assert not callback_data.startswith("model:")
            assert not callback_data.startswith("profile:")
            assert not callback_data.startswith("memory_delete:")
