"""
Обработчик обычных текстовых сообщений — единственное место в
presentation-слое, вызывающее `ProcessUserMessage`. Получает use case
через конструктор (dependency injection, требование 3) — не
импортирует `OpenRouterLLMAdapter`, не читает API-ключ, не выполняет
HTTP-запрос к модели, не формирует системный промпт и не хранит
состояние в глобальной переменной (все требования уже обеспечены тем,
что вся эта работа выполняется внутри `ProcessUserMessage`/адаптера).
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.presentation.telegram.mapper import split_message, to_command
from dekoder.shared.errors import DekoderError
from dekoder.shared.logging import bind_request_context, clear_request_context, get_logger

_logger = get_logger(__name__)

UNEXPECTED_ERROR_MESSAGE = "Произошла непредвиденная ошибка. Попробуйте ещё раз чуть позже."


class TextMessageHandler:
    def __init__(self, process_user_message: ProcessUserMessage) -> None:
        self._process_user_message = process_user_message

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None or message.text is None:
            return

        command = to_command(update)
        bind_request_context(correlation_id=command.correlation_id)
        try:
            result = await self._process_user_message.execute(command)
        except DekoderError as error:
            _logger.warning("process_user_message_failed", error_code=error.code)
            await message.reply_text(error.user_message)
            return
        except Exception:
            _logger.exception("process_user_message_unexpected_error")
            await message.reply_text(UNEXPECTED_ERROR_MESSAGE)
            return
        finally:
            clear_request_context()

        for chunk in split_message(result.response_text):
            await message.reply_text(chunk)
