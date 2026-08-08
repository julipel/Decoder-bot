"""
Обработчики команды `/model` — единственное место в presentation-слое,
вызывающее `ListAvailableModels`/`GetSelectedModel`/`SelectModel`
(Sprint 7, задача S7-07, ADR-7.9).

Получают use case'ы через конструктор (dependency injection, тот же
стиль, что и `ProfileCommandHandler`/`MemoryListCommandHandler`) — не
работают с SQLAlchemy, ORM-моделями, файловым каталогом или
репозиториями напрямую.

Два обработчика (структура копирует `presentation/telegram/handlers/
profile.py` почти буквально, ADR-7.9):
- `ModelCommandHandler` — `CommandHandler("model", ...)`, вызывает
  `GetSelectedModel` (для строки «Текущая модель: …» перед клавиатурой —
  единственный вызывающий код `GetSelectedModel`, ADR-7.7) и
  `ListAvailableModels` (для самой клавиатуры — уже несёт пометку
  активной модели, композиция каталога и персонального выбора, S7-05),
  показывает список моделей каталога с отметкой активной через inline-
  клавиатуру, недоступные модели помечены явно, но всё ещё показаны;
- `ModelSelectionCallbackHandler` — `CallbackQueryHandler` (нажатие
  inline-кнопки), вызывает `SelectModel` и подтверждает переключение
  редактированием исходного сообщения с обновлённым списком; отказ
  (модель недоступна/не найдена — `ApplicationError` из `SelectModel`,
  ADR-7.9) не портит исходный список — сообщение не редактируется,
  пользователь видит всплывающее уведомление (`query.answer(...,
  show_alert=True)`).

`callback_data` кодирует только `model_id` (`f"model:{model_id.value}"`,
`_build_model_keyboard`/`_parse_model_callback_data`) — не сериализует
весь объект модели. Префикс `model:` дизъюнктен с уже занятыми
`profile:`/`memory_delete:` (ADR-7.9).

`GetSelectedModelResult.model is None`/`ApplicationError` из `SelectModel`
— штатные/явные отрицательные исходы, обрабатываются явно, не как
непредвиденные ошибки. `DekoderError` → `error.user_message`; любое
другое исключение → нейтральное сообщение + `_logger.exception`, без
утечки внутренних деталей пользователю — тот же принцип, что и у
`ProfileCommandHandler`/`NewConversationHandler`.
"""

from __future__ import annotations

from collections.abc import Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from dekoder.application.model_catalog.dto import ListAvailableModelsCommand
from dekoder.application.model_catalog.use_cases.get_selected_model import GetSelectedModel
from dekoder.application.model_catalog.use_cases.list_models import ListAvailableModels
from dekoder.application.model_catalog.use_cases.select_model import SelectModel
from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.model_catalog.entities import AIModel
from dekoder.domain.model_catalog.enums import ModelAvailability
from dekoder.presentation.telegram.mapper import (
    to_get_selected_model_command,
    to_list_available_models_command,
    to_select_model_command,
)
from dekoder.shared.errors import DekoderError
from dekoder.shared.logging import bind_request_context, clear_request_context, get_logger

_logger = get_logger(__name__)

MODEL_LIST_MESSAGE = "Выберите модель:"
MODEL_CURRENT_MESSAGE_TEMPLATE = "Текущая модель: {name}\n\n{list_message}"
MODEL_ACTIVE_SUFFIX = " (текущая)"
MODEL_UNAVAILABLE_SUFFIX = " (недоступна)"
MODEL_SELECTED_MESSAGE_TEMPLATE = "Активна модель: {name}"
MODEL_NOT_FOUND_MESSAGE = "Эта модель больше недоступна. Отправьте /model, чтобы увидеть актуальный список."
UNEXPECTED_ERROR_MESSAGE = "Произошла непредвиденная ошибка. Попробуйте ещё раз чуть позже."

_CALLBACK_DATA_PREFIX = "model:"


def _build_model_keyboard(models: Sequence[AIModel], active_model_id: ModelId | None) -> InlineKeyboardMarkup:
    """
    Одна кнопка на модель; активная модель отмечена текстовым суффиксом
    (не эмодзи/иконкой, по образцу `profile.py`), недоступная —
    дополнительной пометкой «(недоступна)» (ADR-7.9) — такие кнопки всё
    ещё показываются, но `SelectModel` отклонит попытку их выбрать.
    """
    rows = []
    for model in models:
        label = model.display_name
        if model.model_id == active_model_id:
            label = f"{label}{MODEL_ACTIVE_SUFFIX}"
        if model.availability is ModelAvailability.UNAVAILABLE:
            label = f"{label}{MODEL_UNAVAILABLE_SUFFIX}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"{_CALLBACK_DATA_PREFIX}{model.model_id.value}")])
    return InlineKeyboardMarkup(rows)


def _parse_model_callback_data(data: str) -> ModelId | None:
    """Разбирает `callback_data` вида `model:<model_id>`; `None` — не наш формат или невалидный (пустой) `model_id`."""
    if not data.startswith(_CALLBACK_DATA_PREFIX):
        return None
    raw_model_id = data[len(_CALLBACK_DATA_PREFIX) :]
    try:
        return ModelId(raw_model_id)
    except ValueError:
        return None


class ModelCommandHandler:
    def __init__(self, list_available_models: ListAvailableModels, get_selected_model: GetSelectedModel) -> None:
        self._list_available_models = list_available_models
        self._get_selected_model = get_selected_model

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return

        selected_command = to_get_selected_model_command(update)
        # Единый correlation_id на оба use-case вызова этого обработчика
        # (Sprint 9, S9-02) — команды строятся из двух отдельных вызовов
        # mapper'а (`to_get_selected_model_command`/
        # `to_list_available_models_command`), каждый со своим свежим
        # `correlation_id`; для наблюдаемости обработки одного `Update`
        # используем `correlation_id` первой (главной для строки «Текущая
        # модель: …») команды, не заводим второй bind/clear на тот же вызов.
        bind_request_context(correlation_id=selected_command.correlation_id)
        try:
            selected_result = await self._get_selected_model.execute(selected_command)
            list_result = await self._list_available_models.execute(to_list_available_models_command(update))
        except DekoderError as error:
            _logger.warning("list_available_models_failed", error_code=error.code)
            await message.reply_text(error.user_message)
            return
        except Exception:
            _logger.exception("list_available_models_unexpected_error")
            await message.reply_text(UNEXPECTED_ERROR_MESSAGE)
            return
        finally:
            clear_request_context()

        if selected_result.model is not None:
            text = MODEL_CURRENT_MESSAGE_TEMPLATE.format(
                name=selected_result.model.display_name, list_message=MODEL_LIST_MESSAGE
            )
        else:
            text = MODEL_LIST_MESSAGE
        keyboard = _build_model_keyboard(list_result.models, active_model_id=list_result.active_model_id)
        await message.reply_text(text, reply_markup=keyboard)


class ModelSelectionCallbackHandler:
    def __init__(self, select_model: SelectModel, list_available_models: ListAvailableModels) -> None:
        self._select_model = select_model
        self._list_available_models = list_available_models

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None or query.data is None:
            return

        model_id = _parse_model_callback_data(query.data)
        if model_id is None:
            # Ровно один вызов `query.answer(...)` за обработку callback'а
            # (Telegram отклоняет повторный ответ на тот же callback) — в
            # отличие от `ProfileSelectionCallbackHandler` (там всегда
            # безусловный `query.answer()` + `edit_message_text` для
            # ошибок), здесь отказ передаётся именно через
            # `show_alert=True`, чтобы не портить исходный список (ADR-7.9).
            await query.answer(MODEL_NOT_FOUND_MESSAGE, show_alert=True)
            return

        command = to_select_model_command(update, model_id)
        bind_request_context(correlation_id=command.correlation_id)
        try:
            result = await self._select_model.execute(command)
        except DekoderError as error:
            # Отказ (модель недоступна/не найдена) не портит исходный
            # список — сообщение не редактируется (ADR-7.9), пользователь
            # видит только всплывающее уведомление.
            _logger.warning("select_model_failed", error_code=error.code)
            await query.answer(error.user_message, show_alert=True)
            return
        except Exception:
            _logger.exception("select_model_unexpected_error")
            await query.answer(UNEXPECTED_ERROR_MESSAGE, show_alert=True)
            return
        finally:
            clear_request_context()

        await query.answer()
        # Реиспользуем уже разрешённый `command.telegram_user_id`
        # (`update.callback_query.from_user`, ADR-7.9) вместо повторного
        # обхода `Update` через `to_list_available_models_command()` (тот
        # опирается на `update.effective_user`, который для callback-only
        # `Update` фактически совпадает, но не должен становиться вторым
        # источником истины). `correlation_id` (Sprint 9, S9-02) —
        # переиспользуем `command.correlation_id`, а не заводим новый: это
        # тот же логический запрос (нажатие кнопки выбора модели).
        bind_request_context(correlation_id=command.correlation_id)
        try:
            list_result = await self._list_available_models.execute(
                ListAvailableModelsCommand(
                    telegram_user_id=command.telegram_user_id,
                    correlation_id=command.correlation_id,
                )
            )
        finally:
            clear_request_context()
        keyboard = _build_model_keyboard(list_result.models, active_model_id=list_result.active_model_id)
        await query.edit_message_text(
            MODEL_SELECTED_MESSAGE_TEMPLATE.format(name=result.model.display_name), reply_markup=keyboard
        )
