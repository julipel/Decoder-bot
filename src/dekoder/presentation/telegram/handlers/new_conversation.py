"""
Обработчик команды `/new` — единственное место в presentation-слое,
вызывающее `StartNewConversation` (Sprint 2, задача S2-08).

Получает use case через конструктор (dependency injection, тот же стиль,
что и `TextMessageHandler` — `presentation/telegram/handlers/messages.py`)
— не работает с SQLAlchemy, ORM-моделями или репозиториями напрямую, не
закрывает и не создаёт диалог самостоятельно: вся эта работа выполняется
внутри `StartNewConversation.execute()`. Этот файл только извлекает
`telegram_user_id` (через `mapper.py::to_start_new_conversation_command`),
вызывает use case и переводит его результат в текстовый ответ
пользователю.

`StartNewConversationResult.conversation_id is None` означает «пользователь
ещё не обращался к боту» (`StartNewConversation` намеренно не создаёт
пользователя автоматически, задача S2-07) — штатный успешный исход, не
ошибка: пользователю отправляется нейтральное сообщение вместо
подтверждения нового диалога.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from dekoder.application.conversation.use_cases.start_new_conversation import StartNewConversation
from dekoder.presentation.telegram.mapper import to_start_new_conversation_command
from dekoder.shared.errors import DekoderError
from dekoder.shared.logging import bind_request_context, clear_request_context, get_logger

_logger = get_logger(__name__)

NEW_CONVERSATION_STARTED_MESSAGE = "Начат новый диалог. История предыдущего диалога сохранена."
NO_PREVIOUS_INTERACTION_MESSAGE = "Мы ещё не начинали диалог. Отправьте обычное сообщение, чтобы начать."
UNEXPECTED_ERROR_MESSAGE = "Произошла непредвиденная ошибка. Попробуйте ещё раз чуть позже."


class NewConversationHandler:
    def __init__(self, start_new_conversation: StartNewConversation) -> None:
        self._start_new_conversation = start_new_conversation

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return

        command = to_start_new_conversation_command(update)
        bind_request_context(correlation_id=command.correlation_id)
        try:
            result = await self._start_new_conversation.execute(command)
        except DekoderError as error:
            _logger.warning("start_new_conversation_failed", error_code=error.code)
            await message.reply_text(error.user_message)
            return
        except Exception:
            _logger.exception("start_new_conversation_unexpected_error")
            await message.reply_text(UNEXPECTED_ERROR_MESSAGE)
            return
        finally:
            clear_request_context()

        if result.conversation_id is None:
            await message.reply_text(NO_PREVIOUS_INTERACTION_MESSAGE)
            return

        await message.reply_text(NEW_CONVERSATION_STARTED_MESSAGE)
