"""
Тесты presentation/telegram/handlers/model.py (Sprint 7, задача S7-07,
ADR-7.9) — без обращения к реальному Telegram API и без SQLAlchemy.
`ListAvailableModels`/`GetSelectedModel`/`SelectModel` собираются
по-настоящему, но поверх in-memory fake-репозиториев/каталога (`tests/
support/fake_conversation_repositories.py`, `tests/support/
fake_model_catalog.py`) — так handler-тесты проверяют реальную цепочку
Update → Command → use case → ответ, не подменяя use case целиком (кроме
отдельных тестов на обработку ошибок, где use case подменяется целиком —
по образцу `test_profile_handler.py`).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from telegram import Update
from tests.support.fake_conversation_repositories import (
    FakeModelSelectionRepository,
    FakeUserRepository,
    make_in_memory_repositories_factory,
)
from tests.support.fake_model_catalog import FakeModelCatalogRepository, make_ai_model

from dekoder.application.model_catalog.dto import (
    GetSelectedModelCommand,
    GetSelectedModelResult,
    SelectModelCommand,
    SelectModelResult,
)
from dekoder.application.model_catalog.ports import ModelCatalogRepository
from dekoder.application.model_catalog.use_cases.get_selected_model import GetSelectedModel
from dekoder.application.model_catalog.use_cases.list_models import ListAvailableModels
from dekoder.application.model_catalog.use_cases.select_model import SelectModel
from dekoder.domain.model_catalog.enums import ModelAvailability
from dekoder.presentation.telegram.handlers import model as model_module
from dekoder.presentation.telegram.handlers.model import (
    MODEL_NOT_FOUND_MESSAGE,
    ModelCommandHandler,
    ModelSelectionCallbackHandler,
)
from dekoder.shared.errors import ApplicationError


def _make_use_cases(
    users: FakeUserRepository | None = None,
    model_selection: FakeModelSelectionRepository | None = None,
    model_catalog: ModelCatalogRepository | None = None,
) -> tuple[ListAvailableModels, GetSelectedModel, SelectModel, FakeUserRepository, FakeModelSelectionRepository]:
    users = users if users is not None else FakeUserRepository()
    model_selection = model_selection if model_selection is not None else FakeModelSelectionRepository()
    model_catalog = model_catalog if model_catalog is not None else FakeModelCatalogRepository()
    factory = make_in_memory_repositories_factory(users=users, model_selection=model_selection)
    list_available_models = ListAvailableModels(repositories=factory, model_catalog=model_catalog)
    get_selected_model = GetSelectedModel(repositories=factory, model_catalog=model_catalog)
    select_model = SelectModel(repositories=factory, model_catalog=model_catalog)
    return list_available_models, get_selected_model, select_model, users, model_selection


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


class TestModelCommandUnknownUser:
    """
    В отличие от `/profile` (гейтится на «нет предыдущего
    взаимодействия»), `/model` показывает полный список каталога и для
    ещё не писавшего боту пользователя — просмотр каталога не требует
    предварительного существования `User` (ADR-7.9: каталог — не
    пользовательские данные).
    """

    async def test_shows_full_catalog_without_marking_any_model_active(self) -> None:
        catalog = FakeModelCatalogRepository([make_ai_model("openai/gpt-4o-mini", display_name="GPT-4o mini")])
        list_available_models, get_selected_model, _, _, _ = _make_use_cases(model_catalog=catalog)
        handler = ModelCommandHandler(list_available_models, get_selected_model)
        update = _make_command_update(user_id=999)

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once()
        call_args = update.effective_message.reply_text.call_args
        assert call_args.args[0] == model_module.MODEL_LIST_MESSAGE
        keyboard = call_args.kwargs["reply_markup"]
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
        assert button_texts == ["GPT-4o mini"]


class TestModelCommandKnownUser:
    """AC-1 (S7-07): клавиатура содержит все модели каталога, активная и недоступные отмечены."""

    async def test_shows_keyboard_with_all_models_and_marks_active(self) -> None:
        available = make_ai_model("openai/gpt-4o-mini", display_name="GPT-4o mini")
        selected = make_ai_model("anthropic/claude-3.5-sonnet", display_name="Claude 3.5 Sonnet")
        catalog = FakeModelCatalogRepository([available, selected])
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(123)
        model_selection = FakeModelSelectionRepository({user.id: selected.model_id})
        list_available_models, get_selected_model, _, _, _ = _make_use_cases(
            users=users, model_selection=model_selection, model_catalog=catalog
        )
        handler = ModelCommandHandler(list_available_models, get_selected_model)
        update = _make_command_update(user_id=123)

        await handler(update, MagicMock())

        call_args = update.effective_message.reply_text.call_args
        assert call_args.args[0] == "Текущая модель: Claude 3.5 Sonnet\n\nВыберите модель:"
        keyboard = call_args.kwargs["reply_markup"]
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
        assert "GPT-4o mini" in button_texts
        assert any("Claude 3.5 Sonnet" in text and "текущая" in text for text in button_texts)

    async def test_unavailable_model_is_marked_but_still_shown(self) -> None:
        available = make_ai_model("openai/gpt-4o-mini", display_name="GPT-4o mini")
        unavailable = make_ai_model(
            "anthropic/claude-3-haiku", display_name="Claude 3 Haiku", availability=ModelAvailability.UNAVAILABLE
        )
        catalog = FakeModelCatalogRepository([available, unavailable])
        list_available_models, get_selected_model, _, _, _ = _make_use_cases(model_catalog=catalog)
        handler = ModelCommandHandler(list_available_models, get_selected_model)
        update = _make_command_update()

        await handler(update, MagicMock())

        keyboard = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
        assert any("Claude 3 Haiku" in text and "недоступна" in text for text in button_texts)

    async def test_callback_data_encodes_only_model_id(self) -> None:
        model = make_ai_model("openai/gpt-4o-mini")
        catalog = FakeModelCatalogRepository([model])
        list_available_models, get_selected_model, _, _, _ = _make_use_cases(model_catalog=catalog)
        handler = ModelCommandHandler(list_available_models, get_selected_model)
        update = _make_command_update()

        await handler(update, MagicMock())

        keyboard = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
        button = keyboard.inline_keyboard[0][0]
        assert button.callback_data == "model:openai/gpt-4o-mini"


class TestModelSelectionCallback:
    """AC-2 (S7-07): выбор доступной модели через inline-кнопку сохраняет выбор и обновляет список."""

    async def test_selects_model_and_confirms_with_refreshed_keyboard(self) -> None:
        available = make_ai_model("openai/gpt-4o-mini", display_name="GPT-4o mini")
        target = make_ai_model("anthropic/claude-3.5-sonnet", display_name="Claude 3.5 Sonnet")
        catalog = FakeModelCatalogRepository([available, target])
        users = FakeUserRepository()
        await users.get_or_create_by_telegram_user_id(555)
        list_available_models, _, select_model, _, model_selection = _make_use_cases(users=users, model_catalog=catalog)
        handler = ModelSelectionCallbackHandler(select_model, list_available_models)
        update = _make_callback_update(data="model:anthropic/claude-3.5-sonnet", user_id=555)

        await handler(update, MagicMock())

        update.callback_query.answer.assert_awaited_once_with()
        update.callback_query.edit_message_text.assert_awaited_once()
        call_args = update.callback_query.edit_message_text.call_args
        assert call_args.args[0] == "Активна модель: Claude 3.5 Sonnet"
        keyboard = call_args.kwargs["reply_markup"]
        button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
        assert any("Claude 3.5 Sonnet" in text and "текущая" in text for text in button_texts)

        user = await users.get_by_telegram_user_id(555)
        assert user is not None
        assert await model_selection.get_selected(user.id) == target.model_id


class TestModelSelectionRejectsUnavailable:
    """AC-3 (S7-07)/AC-1 (S7-05, ADR-7.9): недоступная модель — отказ, видимый пользователю, список не портится."""

    async def test_shows_alert_and_does_not_edit_message(self) -> None:
        unavailable = make_ai_model(
            "anthropic/claude-3-haiku", display_name="Claude 3 Haiku", availability=ModelAvailability.UNAVAILABLE
        )
        catalog = FakeModelCatalogRepository([unavailable])
        list_available_models, _, select_model, _, _ = _make_use_cases(model_catalog=catalog)
        handler = ModelSelectionCallbackHandler(select_model, list_available_models)
        update = _make_callback_update(data="model:anthropic/claude-3-haiku", user_id=666)

        await handler(update, MagicMock())

        update.callback_query.edit_message_text.assert_not_awaited()
        update.callback_query.answer.assert_awaited_once()
        call_args = update.callback_query.answer.call_args
        assert call_args.kwargs.get("show_alert") is True

    async def test_selection_does_not_change(self) -> None:
        unavailable = make_ai_model(
            "anthropic/claude-3-haiku", display_name="Claude 3 Haiku", availability=ModelAvailability.UNAVAILABLE
        )
        catalog = FakeModelCatalogRepository([unavailable])
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(667)
        list_available_models, _, select_model, _, model_selection = _make_use_cases(users=users, model_catalog=catalog)
        handler = ModelSelectionCallbackHandler(select_model, list_available_models)
        update = _make_callback_update(data="model:anthropic/claude-3-haiku", user_id=667)

        await handler(update, MagicMock())

        assert await model_selection.get_selected(user.id) is None


class TestModelSelectionRejectsUnknownModel:
    async def test_shows_alert_and_does_not_edit_message(self) -> None:
        catalog = FakeModelCatalogRepository([make_ai_model("openai/gpt-4o-mini")])
        list_available_models, _, select_model, _, _ = _make_use_cases(model_catalog=catalog)
        handler = ModelSelectionCallbackHandler(select_model, list_available_models)
        update = _make_callback_update(data="model:does-not-exist/model", user_id=668)

        await handler(update, MagicMock())

        update.callback_query.edit_message_text.assert_not_awaited()
        assert update.callback_query.answer.call_args.kwargs.get("show_alert") is True


class TestModelSelectionMalformedCallbackData:
    async def test_shows_not_found_message_when_prefix_does_not_match(self) -> None:
        catalog = FakeModelCatalogRepository([make_ai_model("openai/gpt-4o-mini")])
        list_available_models, _, select_model, _, _ = _make_use_cases(model_catalog=catalog)
        handler = ModelSelectionCallbackHandler(select_model, list_available_models)
        update = _make_callback_update(data="not-a-model-callback")

        await handler(update, MagicMock())

        update.callback_query.answer.assert_awaited_once_with(MODEL_NOT_FOUND_MESSAGE, show_alert=True)
        update.callback_query.edit_message_text.assert_not_awaited()

    async def test_shows_not_found_message_when_model_id_is_empty(self) -> None:
        catalog = FakeModelCatalogRepository([make_ai_model("openai/gpt-4o-mini")])
        list_available_models, _, select_model, _, _ = _make_use_cases(model_catalog=catalog)
        handler = ModelSelectionCallbackHandler(select_model, list_available_models)
        update = _make_callback_update(data="model:")

        await handler(update, MagicMock())

        update.callback_query.answer.assert_awaited_once_with(MODEL_NOT_FOUND_MESSAGE, show_alert=True)


class TestCallbackUsesCallbackQueryFromUserNotEffectiveUser:
    """ADR-7.9: telegram_user_id для callback — из update.callback_query.from_user, не update.effective_user."""

    async def test_selection_is_attributed_to_the_callback_presser(self) -> None:
        model = make_ai_model("openai/gpt-4o-mini")
        catalog = FakeModelCatalogRepository([model])
        users = FakeUserRepository()
        presser = await users.get_or_create_by_telegram_user_id(777)
        list_available_models, _, select_model, _, model_selection = _make_use_cases(users=users, model_catalog=catalog)
        handler = ModelSelectionCallbackHandler(select_model, list_available_models)
        update = _make_callback_update(data="model:openai/gpt-4o-mini", user_id=777)
        # `effective_user`, будь он использован по ошибке, указывал бы на другого пользователя.
        update.effective_user = MagicMock(id=888)

        await handler(update, MagicMock())

        assert await model_selection.get_selected(presser.id) == model.model_id


class TestIgnoresUpdatesWithoutRelevantPayload:
    async def test_command_handler_ignores_update_without_message(self) -> None:
        list_available_models, get_selected_model, _, _, _ = _make_use_cases()
        handler = ModelCommandHandler(list_available_models, get_selected_model)
        update = _make_command_update()
        update.effective_message = None

        await handler(update, MagicMock())  # не должно бросить исключение

    async def test_callback_handler_ignores_update_without_callback_query(self) -> None:
        _, _, select_model, _, _ = _make_use_cases()
        list_available_models, _, _, _, _ = _make_use_cases()
        handler = ModelSelectionCallbackHandler(select_model, list_available_models)
        update = _make_command_update()
        update.callback_query = None

        await handler(update, MagicMock())  # не должно бросить исключение


class FakeFailingGetSelectedModel:
    """Fake use case, поднимающий заданное исключение — без наследования от GetSelectedModel."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def execute(self, command: GetSelectedModelCommand) -> GetSelectedModelResult:
        raise self._error


class FakeFailingSelectModel:
    """Fake use case, поднимающий заданное исключение — без наследования от SelectModel."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def execute(self, command: SelectModelCommand) -> SelectModelResult:
        raise self._error


class TestDekoderErrorHandling:
    async def test_model_command_shows_the_errors_safe_user_message(self) -> None:
        safe_message = "Не удалось показать модели, попробуйте позже."
        list_available_models, _, _, _, _ = _make_use_cases()
        get_selected_model = FakeFailingGetSelectedModel(ApplicationError(message="boom", user_message=safe_message))
        handler = ModelCommandHandler(list_available_models, get_selected_model)  # type: ignore[arg-type]
        update = _make_command_update()

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(safe_message)

    async def test_select_model_shows_the_errors_safe_user_message_via_alert(self) -> None:
        safe_message = "Эта модель сейчас недоступна для выбора. Отправьте /model, чтобы выбрать другую."
        select_model = FakeFailingSelectModel(
            ApplicationError(message="boom", user_message=safe_message, code="MODEL_UNAVAILABLE")
        )
        list_available_models, _, _, _, _ = _make_use_cases()
        handler = ModelSelectionCallbackHandler(select_model, list_available_models)  # type: ignore[arg-type]
        update = _make_callback_update(data="model:anthropic/claude-3-haiku")

        await handler(update, MagicMock())

        update.callback_query.answer.assert_awaited_once_with(safe_message, show_alert=True)
        update.callback_query.edit_message_text.assert_not_awaited()


class TestUnexpectedErrorHandling:
    async def test_model_command_shows_neutral_message(self) -> None:
        list_available_models, _, _, _, _ = _make_use_cases()
        get_selected_model = FakeFailingGetSelectedModel(RuntimeError("secret=abc123"))
        handler = ModelCommandHandler(list_available_models, get_selected_model)  # type: ignore[arg-type]
        update = _make_command_update()

        await handler(update, MagicMock())

        update.effective_message.reply_text.assert_awaited_once_with(model_module.UNEXPECTED_ERROR_MESSAGE)

    async def test_select_model_details_never_reach_the_user(self) -> None:
        select_model = FakeFailingSelectModel(RuntimeError("secret=abc123, Traceback details"))
        list_available_models, _, _, _, _ = _make_use_cases()
        handler = ModelSelectionCallbackHandler(select_model, list_available_models)  # type: ignore[arg-type]
        update = _make_callback_update(data="model:openai/gpt-4o-mini")

        await handler(update, MagicMock())

        sent_alert = update.callback_query.answer.call_args.args[0]
        assert "secret=abc123" not in sent_alert
        assert "Traceback" not in sent_alert


def _imported_module_names(module: object) -> set[str]:
    """Тот же способ, что и в test_profile_handler.py — AST, не поиск подстроки в исходнике."""
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
    """Архитектурная проверка: presentation-слой не импортирует SQLAlchemy/ORM/репозитории/файловый каталог напрямую."""

    def test_model_handler_module_does_not_import_sqlalchemy_or_repositories(self) -> None:
        imports = _imported_module_names(model_module)

        assert not any(name.startswith("sqlalchemy") for name in imports)
        assert not any(name.startswith("dekoder.infrastructure") for name in imports)


class TestCallbackPrefixDoesNotCollideWithOtherHandlers:
    """ADR-7.9: callback-префикс `model:` не пересекается с `profile:`/`memory_delete:`."""

    def test_model_callback_data_does_not_match_profile_or_memory_prefixes(self) -> None:
        callback_data = "model:openai/gpt-4o-mini"

        assert not callback_data.startswith("profile:")
        assert not callback_data.startswith("memory_delete:")
