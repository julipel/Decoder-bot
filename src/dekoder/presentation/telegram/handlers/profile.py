"""
Обработчики команды `/profile` — единственное место в presentation-слое,
вызывающее `ListProfiles`/`GetActiveProfile`/`SelectProfile` (Sprint 3,
задача S3-08).

Получают use case'ы через конструктор (dependency injection, тот же
стиль, что и `NewConversationHandler`/`ClearConversationHandler`) — не
работают с SQLAlchemy, ORM-моделями или репозиториями напрямую.

Два обработчика:
- `ProfileCommandHandler` — `CommandHandler("profile", ...)`, показывает
  список профилей каталога с отметкой активного через inline-клавиатуру;
- `ProfileSelectionCallbackHandler` — первый в проекте
  `CallbackQueryHandler` (нажатие inline-кнопки), вызывает
  `SelectProfile` и подтверждает переключение редактированием исходного
  сообщения.

`callback_data` кодирует только `profile_id` (`f"profile:{profile_id}"`,
`_build_profile_keyboard`/`_parse_profile_callback_data`) — не
сериализует весь объект профиля.

`GetActiveProfileResult.profile is None`/`SelectProfileResult.status in
{UNKNOWN_USER, UNKNOWN_PROFILE}` — штатные отрицательные исходы
(«пользователь ещё не обращался к боту», «устаревший/несуществующий
`profile_id`»), обрабатываются явно, не как ошибки. `DekoderError` →
`error.user_message`; любое другое исключение → нейтральное сообщение +
`_logger.exception`, без утечки внутренних деталей пользователю — тот же
принцип, что и у `NewConversationHandler`.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from dekoder.application.profile.dto import SelectProfileStatus
from dekoder.application.profile.use_cases.get_active_profile import GetActiveProfile
from dekoder.application.profile.use_cases.list_profiles import ListProfiles
from dekoder.application.profile.use_cases.select_profile import SelectProfile
from dekoder.domain.profile.entities import UserProfile
from dekoder.presentation.telegram.mapper import to_get_active_profile_command, to_select_profile_command
from dekoder.shared.errors import DekoderError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)

PROFILE_LIST_MESSAGE = "Выберите профиль:"
PROFILE_ACTIVE_SUFFIX = " (текущий)"
PROFILE_SELECTED_MESSAGE_TEMPLATE = "Активный профиль: {name}"
NO_PREVIOUS_INTERACTION_MESSAGE = "Мы ещё не начинали диалог. Отправьте обычное сообщение, чтобы начать."
PROFILE_NOT_FOUND_MESSAGE = "Этот профиль больше недоступен. Отправьте /profile, чтобы увидеть актуальный список."
UNEXPECTED_ERROR_MESSAGE = "Произошла непредвиденная ошибка. Попробуйте ещё раз чуть позже."

_CALLBACK_DATA_PREFIX = "profile:"


def _build_profile_keyboard(profiles: Sequence[UserProfile], active_profile_id: UUID) -> InlineKeyboardMarkup:
    """Одна кнопка на профиль; активный профиль отмечен суффиксом в тексте кнопки, не эмодзи/иконкой."""
    rows = []
    for profile in profiles:
        label = profile.name
        if profile.id == active_profile_id:
            label = f"{label}{PROFILE_ACTIVE_SUFFIX}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"{_CALLBACK_DATA_PREFIX}{profile.id}")])
    return InlineKeyboardMarkup(rows)


def _parse_profile_callback_data(data: str) -> UUID | None:
    """Разбирает `callback_data` вида `profile:<uuid>`; `None` — не наш формат или невалидный UUID."""
    if not data.startswith(_CALLBACK_DATA_PREFIX):
        return None
    raw_profile_id = data[len(_CALLBACK_DATA_PREFIX) :]
    try:
        return UUID(raw_profile_id)
    except ValueError:
        return None


class ProfileCommandHandler:
    def __init__(self, list_profiles: ListProfiles, get_active_profile: GetActiveProfile) -> None:
        self._list_profiles = list_profiles
        self._get_active_profile = get_active_profile

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return

        command = to_get_active_profile_command(update)
        try:
            active_result = await self._get_active_profile.execute(command)
        except DekoderError as error:
            _logger.warning("get_active_profile_failed", error_code=error.code)
            await message.reply_text(error.user_message)
            return
        except Exception:
            _logger.exception("get_active_profile_unexpected_error")
            await message.reply_text(UNEXPECTED_ERROR_MESSAGE)
            return

        if active_result.profile is None:
            await message.reply_text(NO_PREVIOUS_INTERACTION_MESSAGE)
            return

        try:
            profiles_result = await self._list_profiles.execute()
        except DekoderError as error:
            _logger.warning("list_profiles_failed", error_code=error.code)
            await message.reply_text(error.user_message)
            return
        except Exception:
            _logger.exception("list_profiles_unexpected_error")
            await message.reply_text(UNEXPECTED_ERROR_MESSAGE)
            return

        keyboard = _build_profile_keyboard(profiles_result.profiles, active_profile_id=active_result.profile.id)
        await message.reply_text(PROFILE_LIST_MESSAGE, reply_markup=keyboard)


class ProfileSelectionCallbackHandler:
    def __init__(self, select_profile: SelectProfile) -> None:
        self._select_profile = select_profile

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None or query.data is None:
            return

        profile_id = _parse_profile_callback_data(query.data)
        await query.answer()
        if profile_id is None:
            await query.edit_message_text(PROFILE_NOT_FOUND_MESSAGE)
            return

        command = to_select_profile_command(update, profile_id)
        try:
            result = await self._select_profile.execute(command)
        except DekoderError as error:
            _logger.warning("select_profile_failed", error_code=error.code)
            await query.edit_message_text(error.user_message)
            return
        except Exception:
            _logger.exception("select_profile_unexpected_error")
            await query.edit_message_text(UNEXPECTED_ERROR_MESSAGE)
            return

        if result.status is SelectProfileStatus.UNKNOWN_USER:
            await query.edit_message_text(NO_PREVIOUS_INTERACTION_MESSAGE)
            return
        if result.status is SelectProfileStatus.UNKNOWN_PROFILE:
            await query.edit_message_text(PROFILE_NOT_FOUND_MESSAGE)
            return

        assert result.profile is not None  # SELECTED всегда несёт профиль (application/profile/dto.py)
        await query.edit_message_text(PROFILE_SELECTED_MESSAGE_TEMPLATE.format(name=result.profile.name))
