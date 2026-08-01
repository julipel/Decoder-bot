"""
Обработчик команды `/clear` — единственное место в presentation-слое,
вызывающее `ClearConversation` (Sprint 2, задача S2-10).

Получает use case через конструктор (dependency injection, тот же стиль,
что и `NewConversationHandler`/`TextMessageHandler`) — не работает с
SQLAlchemy, ORM-моделями или репозиториями напрямую, не закрывает и не
создаёт диалог самостоятельно: вся эта работа (или, точнее, её
сознательное отсутствие — `ClearConversation` не закрывает и не создаёт
`Conversation`) выполняется внутри `ClearConversation.execute()`. Этот
файл только извлекает `telegram_user_id` (через
`mapper.py::to_clear_conversation_command`), вызывает use case и
переводит его результат (`ClearConversationResult.status`) в текстовый
ответ пользователю.

`ClearConversationResult.status` различает три исхода
(`application/conversation/dto.py::ClearConversationStatus`), каждому
соответствует отдельное сообщение:
- `CLEARED` — история очищена, диалог продолжается;
- `ALREADY_EMPTY` — активный диалог есть, но истории уже не было;
- `NO_ACTIVE_CONVERSATION` — пользователь ещё не обращался к боту или у
  него нет активного диалога — штатный успешный исход, не ошибка.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from dekoder.application.conversation.dto import ClearConversationStatus
from dekoder.application.conversation.use_cases.clear_conversation import ClearConversation
from dekoder.presentation.telegram.mapper import to_clear_conversation_command
from dekoder.shared.errors import DekoderError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)

CONVERSATION_CLEARED_MESSAGE = "История текущего диалога очищена. Можно продолжать общение."
CONVERSATION_ALREADY_EMPTY_MESSAGE = "История текущего диалога уже была пуста."
NO_ACTIVE_CONVERSATION_MESSAGE = "Активный диалог не найден. Отправьте обычное сообщение, чтобы начать."
UNEXPECTED_ERROR_MESSAGE = "Произошла непредвиденная ошибка. Попробуйте ещё раз чуть позже."

_STATUS_MESSAGES = {
    ClearConversationStatus.CLEARED: CONVERSATION_CLEARED_MESSAGE,
    ClearConversationStatus.ALREADY_EMPTY: CONVERSATION_ALREADY_EMPTY_MESSAGE,
    ClearConversationStatus.NO_ACTIVE_CONVERSATION: NO_ACTIVE_CONVERSATION_MESSAGE,
}


class ClearConversationHandler:
    def __init__(self, clear_conversation: ClearConversation) -> None:
        self._clear_conversation = clear_conversation

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return

        command = to_clear_conversation_command(update)
        try:
            result = await self._clear_conversation.execute(command)
        except DekoderError as error:
            _logger.warning("clear_conversation_failed", error_code=error.code)
            await message.reply_text(error.user_message)
            return
        except Exception:
            _logger.exception("clear_conversation_unexpected_error")
            await message.reply_text(UNEXPECTED_ERROR_MESSAGE)
            return

        await message.reply_text(_STATUS_MESSAGES[result.status])
