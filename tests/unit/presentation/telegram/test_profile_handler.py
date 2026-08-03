"""
Тесты presentation/telegram/handlers/profile.py (Sprint 3, задача S3-08)
— без обращения к реальному Telegram API и без SQLAlchemy.
`ListProfiles`/`GetActiveProfile`/`SelectProfile` собираются
по-настоящему, но поверх in-memory fake-репозиториев (`tests/support/
fake_conversation_repositories.py`, тот же helper, что и тесты
`NewConversationHandler`/`ClearConversationHandler`) — так handler-тесты
проверяют реальную цепочку Update → Command → use case → ответ, не
подменяя use case целиком (кроме отдельных тестов на обработку ошибок,
где use case подменяется полностью — по образцу
`test_new_conversation_handler.py::FakeFailingStartNewConversation`).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from telegram import Update
from tests.support.fake_conversation_repositories import (
    FakeProfileRepository,
    FakeUserRepository,
    make_default_profile,
    make_in_memory_repositories_factory,
)

from dekoder.application.profile.dto import (
    GetActiveProfileCommand,
    GetActiveProfileResult,
    ListProfilesResult,
    SelectProfileCommand,
    SelectProfileResult,
)
from dekoder.application.profile.use_cases.get_active_profile import GetActiveProfile
from dekoder.application.profile.use_cases.list_profiles import ListProfiles
from dekoder.application.profile.use_cases.select_profile import SelectProfile
from dekoder.presentation.telegram.handlers import profile as profile_module
from dekoder.presentation.telegram.handlers.profile import (
    NO_PREVIOUS_INTERACTION_MESSAGE,
    PROFILE_NOT_FOUND_MESSAGE,
    ProfileCommandHandler,
    ProfileSelectionCallbackHandler,
)
from dekoder.shared.errors import ApplicationError


class RecordingListProfiles:
    """Spy, оборачивающий реальный use case, чтобы проверить, вызывался ли он вовсе."""

    def __init__(self, use_case: ListProfiles) -> None:
        self._use_case = use_case
        self.call_count = 0

    async def execute(self) -> ListProfilesResult:
        self.call_count += 1
        return await self._use_case.execute()


def _make_use_cases(
    users: FakeUserRepository | None = None,
    profiles: FakeProfileRepository | None = None,
) -> tuple[RecordingListProfiles, GetActiveProfile, SelectProfile, FakeUserRepository, FakeProfileRepository]:
    users = users if users is not None else FakeUserRepository()
    profiles = profiles if profiles is not None else FakeProfileRepository()
    factory = make_in_memory_repositories_factory(users=users, profiles=profiles)
    list_profiles = RecordingListProfiles(ListProfiles(repositories=factory))
    get_active_profile = GetActiveProfile(repositories=factory)
    select_profile = SelectProfile(repositories=factory)
    return list_profiles, get_active_profile, select_profile, users, profiles


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


class TestProfileCommandUnknownUser:
    """AC-3: telegram_user_id, ни разу не писавший боту, -> нейтральное сообщение, клавиатура не отправляется."""

    async def test_shows_no_previous_interaction_message(self) -> None:
        list_profiles, get_active_profile, _, _, _ = _make_use_cases()
        handler = ProfileCommandHandler(list_profiles, get_active_profile)
        update = _make_command_update(user_id=999)

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(NO_PREVIOUS_INTERACTION_MESSAGE)

    async def test_does_not_call_list_profiles(self) -> None:
        list_profiles, get_active_profile, _, _, _ = _make_use_cases()
        handler = ProfileCommandHandler(list_profiles, get_active_profile)

        await handler(_make_command_update(user_id=999), MagicMock())

        assert list_profiles.call_count == 0


class TestProfileCommandKnownUser:
    """AC-1: клавиатура содержит все профили каталога, активный отмечен."""

    async def test_shows_keyboard_with_all_profiles_and_marks_active(self) -> None:
        default_profile = make_default_profile(name="Деловой")
        other_profile = make_default_profile(is_default=False, name="Экспертный")
        profiles = FakeProfileRepository([default_profile, other_profile])
        users = FakeUserRepository()
        await users.get_or_create_by_telegram_user_id(123)
        list_profiles, get_active_profile, _, _, _ = _make_use_cases(users=users, profiles=profiles)
        handler = ProfileCommandHandler(list_profiles, get_active_profile)
        update = _make_command_update(user_id=123)

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once()
        call_args = update.effective_message.reply_text.call_args
        keyboard = call_args.kwargs["reply_markup"]
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
        assert any("Деловой" in text and "текущий" in text for text in button_texts)
        assert any(text == "Экспертный" for text in button_texts)

    async def test_callback_data_encodes_only_profile_id(self) -> None:
        default_profile = make_default_profile(name="Деловой")
        profiles = FakeProfileRepository([default_profile])
        users = FakeUserRepository()
        await users.get_or_create_by_telegram_user_id(123)
        list_profiles, get_active_profile, _, _, _ = _make_use_cases(users=users, profiles=profiles)
        handler = ProfileCommandHandler(list_profiles, get_active_profile)
        update = _make_command_update(user_id=123)

        await handler(update, MagicMock())

        keyboard = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
        button = keyboard.inline_keyboard[0][0]
        assert button.callback_data == f"profile:{default_profile.id}"


class TestProfileSelectionCallback:
    """AC-2: выбор профиля через inline-кнопку вызывает SelectProfile и подтверждает переключение."""

    async def test_selects_profile_and_confirms(self) -> None:
        default_profile = make_default_profile(name="Деловой")
        target_profile = make_default_profile(is_default=False, name="Креативный")
        profiles = FakeProfileRepository([default_profile, target_profile])
        users = FakeUserRepository()
        await users.get_or_create_by_telegram_user_id(555)
        _, _, select_profile, _, _ = _make_use_cases(users=users, profiles=profiles)
        handler = ProfileSelectionCallbackHandler(select_profile)
        update = _make_callback_update(data=f"profile:{target_profile.id}", user_id=555)

        await handler(update, MagicMock())

        update.callback_query.answer.assert_awaited_once()
        update.callback_query.edit_message_text.assert_awaited_once_with("Активный профиль: Креативный")

        active = await profiles.get_active_profile((await users.get_by_telegram_user_id(555)).id)  # type: ignore[union-attr]
        assert active.id == target_profile.id


class TestProfileSelectionUnknownProfile:
    """AC-4: callback с profile_id, не существующим в каталоге -> понятное сообщение, активный профиль не меняется."""

    async def test_shows_profile_not_found_message(self) -> None:
        default_profile = make_default_profile(name="Деловой")
        profiles = FakeProfileRepository([default_profile])
        users = FakeUserRepository()
        await users.get_or_create_by_telegram_user_id(555)
        _, _, select_profile, _, _ = _make_use_cases(users=users, profiles=profiles)
        handler = ProfileSelectionCallbackHandler(select_profile)
        unknown_id = uuid4()
        update = _make_callback_update(data=f"profile:{unknown_id}", user_id=555)

        await handler(update, MagicMock())

        update.callback_query.edit_message_text.assert_awaited_once_with(PROFILE_NOT_FOUND_MESSAGE)

    async def test_active_profile_does_not_change(self) -> None:
        default_profile = make_default_profile(name="Деловой")
        profiles = FakeProfileRepository([default_profile])
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(555)
        _, _, select_profile, _, _ = _make_use_cases(users=users, profiles=profiles)
        handler = ProfileSelectionCallbackHandler(select_profile)
        update = _make_callback_update(data=f"profile:{uuid4()}", user_id=555)

        await handler(update, MagicMock())

        active = await profiles.get_active_profile(user.id)
        assert active.id == default_profile.id


class TestProfileSelectionMalformedCallbackData:
    async def test_shows_profile_not_found_message_when_prefix_does_not_match(self) -> None:
        _, _, select_profile, _, _ = _make_use_cases()
        handler = ProfileSelectionCallbackHandler(select_profile)
        update = _make_callback_update(data="not-a-profile-callback")

        await handler(update, MagicMock())

        update.callback_query.edit_message_text.assert_awaited_once_with(PROFILE_NOT_FOUND_MESSAGE)

    async def test_shows_profile_not_found_message_when_uuid_is_invalid(self) -> None:
        _, _, select_profile, _, _ = _make_use_cases()
        handler = ProfileSelectionCallbackHandler(select_profile)
        update = _make_callback_update(data="profile:not-a-valid-uuid")

        await handler(update, MagicMock())

        update.callback_query.edit_message_text.assert_awaited_once_with(PROFILE_NOT_FOUND_MESSAGE)


class TestProfileSelectionUnknownUser:
    async def test_shows_no_previous_interaction_message(self) -> None:
        default_profile = make_default_profile(name="Деловой")
        profiles = FakeProfileRepository([default_profile])
        _, _, select_profile, _, _ = _make_use_cases(profiles=profiles)
        handler = ProfileSelectionCallbackHandler(select_profile)
        update = _make_callback_update(data=f"profile:{default_profile.id}", user_id=999)

        await handler(update, MagicMock())

        update.callback_query.edit_message_text.assert_awaited_once_with(NO_PREVIOUS_INTERACTION_MESSAGE)


class TestIgnoresUpdatesWithoutRelevantPayload:
    async def test_command_handler_ignores_update_without_message(self) -> None:
        list_profiles, get_active_profile, _, _, _ = _make_use_cases()
        handler = ProfileCommandHandler(list_profiles, get_active_profile)
        update = _make_command_update()
        update.effective_message = None

        await handler(update, MagicMock())  # не должно бросить исключение

    async def test_callback_handler_ignores_update_without_callback_query(self) -> None:
        _, _, select_profile, _, _ = _make_use_cases()
        handler = ProfileSelectionCallbackHandler(select_profile)
        update = _make_command_update()
        update.callback_query = None

        await handler(update, MagicMock())  # не должно бросить исключение


class FakeFailingGetActiveProfile:
    """Fake use case, поднимающий заданное исключение — без наследования от GetActiveProfile."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def execute(self, command: GetActiveProfileCommand) -> GetActiveProfileResult:
        raise self._error


class FakeFailingListProfiles:
    """Fake use case, поднимающий заданное исключение — без наследования от ListProfiles."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def execute(self) -> ListProfilesResult:
        raise self._error


class FakeFailingSelectProfile:
    """Fake use case, поднимающий заданное исключение — без наследования от SelectProfile."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def execute(self, command: SelectProfileCommand) -> SelectProfileResult:
        raise self._error


class TestDekoderErrorHandling:
    async def test_profile_command_shows_the_errors_safe_user_message(self) -> None:
        safe_message = "Не удалось показать профили, попробуйте позже."
        list_profiles, _, _, _, _ = _make_use_cases()
        get_active_profile = FakeFailingGetActiveProfile(ApplicationError(message="boom", user_message=safe_message))
        handler = ProfileCommandHandler(list_profiles, get_active_profile)  # type: ignore[arg-type]
        update = _make_command_update()

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(safe_message)

    async def test_select_profile_shows_the_errors_safe_user_message(self) -> None:
        safe_message = "Не удалось выбрать профиль, попробуйте позже."
        select_profile = FakeFailingSelectProfile(ApplicationError(message="boom", user_message=safe_message))
        handler = ProfileSelectionCallbackHandler(select_profile)  # type: ignore[arg-type]
        update = _make_callback_update(data=f"profile:{uuid4()}")

        await handler(update, MagicMock())

        update.callback_query.edit_message_text.assert_awaited_once_with(safe_message)

    async def test_list_profiles_shows_the_errors_safe_user_message(self) -> None:
        safe_message = "Не удалось показать список профилей, попробуйте позже."
        _, get_active_profile, _, users, _ = _make_use_cases()
        await users.get_or_create_by_telegram_user_id(123)
        list_profiles = FakeFailingListProfiles(ApplicationError(message="boom", user_message=safe_message))
        handler = ProfileCommandHandler(list_profiles, get_active_profile)  # type: ignore[arg-type]
        update = _make_command_update(user_id=123)

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(safe_message)


class TestUnexpectedErrorHandling:
    async def test_profile_command_shows_neutral_message(self) -> None:
        list_profiles, _, _, _, _ = _make_use_cases()
        get_active_profile = FakeFailingGetActiveProfile(RuntimeError("secret=abc123"))
        handler = ProfileCommandHandler(list_profiles, get_active_profile)  # type: ignore[arg-type]
        update = _make_command_update()

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(profile_module.UNEXPECTED_ERROR_MESSAGE)

    async def test_select_profile_details_never_reach_the_user(self) -> None:
        select_profile = FakeFailingSelectProfile(RuntimeError("secret=abc123, Traceback details"))
        handler = ProfileSelectionCallbackHandler(select_profile)  # type: ignore[arg-type]
        update = _make_callback_update(data=f"profile:{uuid4()}")

        await handler(update, MagicMock())

        sent_text = update.callback_query.edit_message_text.call_args.args[0]
        assert "secret=abc123" not in sent_text
        assert "Traceback" not in sent_text


def _imported_module_names(module: object) -> set[str]:
    """Тот же способ, что и в test_new_conversation_handler.py — AST, не поиск подстроки в исходнике."""
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

    def test_profile_handler_module_does_not_import_sqlalchemy_or_repositories(self) -> None:
        imports = _imported_module_names(profile_module)

        assert not any(name.startswith("sqlalchemy") for name in imports)
        assert not any(name.startswith("dekoder.infrastructure") for name in imports)
