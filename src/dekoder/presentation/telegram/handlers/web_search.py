"""
Обработчики команды `/websearch` — персональный переключатель веб-поиска
(внеспринтовая задача, 2026-09-09), структура копирует
`presentation/telegram/handlers/model.py` почти буквально: та же пара
«CommandHandler + CallbackQueryHandler с inline-кнопкой», тот же принцип
обработки ошибок (`DekoderError` → `error.user_message`, прочее →
нейтральное сообщение + `_logger.exception`).

Два обработчика:
- `WebSearchCommandHandler` — `CommandHandler("websearch", ...)`, вызывает
  `GetWebSearchStatus`, показывает текущее состояние и предупреждение о
  цене с inline-кнопкой переключения на противоположное состояние;
- `WebSearchToggleCallbackHandler` — `CallbackQueryHandler`, вызывает
  `SetWebSearchEnabled`, подтверждает переключение редактированием
  исходного сообщения с обновлённым состоянием/кнопкой.

`callback_data` кодирует только целевое состояние (`f"websearch:{'on' if
enabled else 'off'}"`, не весь объект) — префикс `websearch:` дизъюнктен
с уже занятыми `model:`/`profile:`/`memory_delete:`.

Переключатель применяется ко ВСЕМ последующим сообщениям пользователя
независимо от выбранной модели (`application/conversation/ports.py::
WebSearchSettingRepository`) — не команда одноразового действия.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from dekoder.application.conversation.use_cases.get_web_search_status import GetWebSearchStatus
from dekoder.application.conversation.use_cases.set_web_search_enabled import SetWebSearchEnabled
from dekoder.presentation.telegram.mapper import to_get_web_search_status_command, to_set_web_search_enabled_command
from dekoder.shared.errors import DekoderError
from dekoder.shared.logging import bind_request_context, clear_request_context, get_logger

_logger = get_logger(__name__)

WEB_SEARCH_STATUS_MESSAGE_TEMPLATE = (
    "Веб-поиск сейчас {status}. При включении модель перед ответом ищет "
    "актуальную информацию в интернете — работает с любой выбранной "
    "моделью, но такой ответ заметно (в несколько раз) дороже обычного."
)
WEB_SEARCH_STATUS_ENABLED = "включён"
WEB_SEARCH_STATUS_DISABLED = "выключен"
WEB_SEARCH_BUTTON_ENABLE = "Включить веб-поиск"
WEB_SEARCH_BUTTON_DISABLE = "Выключить веб-поиск"
UNEXPECTED_ERROR_MESSAGE = "Произошла непредвиденная ошибка. Попробуйте ещё раз чуть позже."

_CALLBACK_DATA_PREFIX = "websearch:"
_CALLBACK_DATA_ON = f"{_CALLBACK_DATA_PREFIX}on"
_CALLBACK_DATA_OFF = f"{_CALLBACK_DATA_PREFIX}off"


def _build_status_message(enabled: bool) -> str:
    status = WEB_SEARCH_STATUS_ENABLED if enabled else WEB_SEARCH_STATUS_DISABLED
    return WEB_SEARCH_STATUS_MESSAGE_TEMPLATE.format(status=status)


def _build_toggle_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    """Кнопка всегда одна — переключает на противоположное текущему состояние."""
    if enabled:
        button = InlineKeyboardButton(text=WEB_SEARCH_BUTTON_DISABLE, callback_data=_CALLBACK_DATA_OFF)
    else:
        button = InlineKeyboardButton(text=WEB_SEARCH_BUTTON_ENABLE, callback_data=_CALLBACK_DATA_ON)
    return InlineKeyboardMarkup([[button]])


def _parse_web_search_callback_data(data: str) -> bool | None:
    """Разбирает `callback_data` вида `websearch:on`/`websearch:off`; `None` — не наш формат."""
    if data == _CALLBACK_DATA_ON:
        return True
    if data == _CALLBACK_DATA_OFF:
        return False
    return None


class WebSearchCommandHandler:
    def __init__(self, get_web_search_status: GetWebSearchStatus) -> None:
        self._get_web_search_status = get_web_search_status

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return

        command = to_get_web_search_status_command(update)
        bind_request_context(correlation_id=command.correlation_id)
        try:
            result = await self._get_web_search_status.execute(command)
        except DekoderError as error:
            _logger.warning("get_web_search_status_failed", error_code=error.code)
            await message.reply_text(error.user_message)
            return
        except Exception:
            _logger.exception("get_web_search_status_unexpected_error")
            await message.reply_text(UNEXPECTED_ERROR_MESSAGE)
            return
        finally:
            clear_request_context()

        await message.reply_text(
            _build_status_message(result.enabled), reply_markup=_build_toggle_keyboard(result.enabled)
        )


class WebSearchToggleCallbackHandler:
    def __init__(self, set_web_search_enabled: SetWebSearchEnabled) -> None:
        self._set_web_search_enabled = set_web_search_enabled

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None or query.data is None:
            return

        target_enabled = _parse_web_search_callback_data(query.data)
        if target_enabled is None:
            await query.answer(UNEXPECTED_ERROR_MESSAGE, show_alert=True)
            return

        command = to_set_web_search_enabled_command(update, target_enabled)
        bind_request_context(correlation_id=command.correlation_id)
        try:
            result = await self._set_web_search_enabled.execute(command)
        except DekoderError as error:
            _logger.warning("set_web_search_enabled_failed", error_code=error.code)
            await query.answer(error.user_message, show_alert=True)
            return
        except Exception:
            _logger.exception("set_web_search_enabled_unexpected_error")
            await query.answer(UNEXPECTED_ERROR_MESSAGE, show_alert=True)
            return
        finally:
            clear_request_context()

        await query.answer()
        await query.edit_message_text(
            _build_status_message(result.enabled), reply_markup=_build_toggle_keyboard(result.enabled)
        )
