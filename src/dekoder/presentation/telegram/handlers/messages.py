"""
Обработчик обычных текстовых сообщений — единственное место в
presentation-слое, вызывающее `ProcessUserMessage`. Получает use case
через конструктор (dependency injection, требование 3) — не
импортирует `OpenAiCompatibleLLMAdapter`, не читает API-ключ, не выполняет
HTTP-запрос к модели, не формирует системный промпт и не хранит
состояние в глобальной переменной (все требования уже обеспечены тем,
что вся эта работа выполняется внутри `ProcessUserMessage`/адаптера).

Sprint 12: дополнительно принимает `CreateMemoryRecordUseCase` — не для
обычного диалога, а чтобы завершить двухшаговый сценарий `/remember` без
аргумента (`handlers/memory.py::RememberCommandHandler`,
`PENDING_REMEMBER_KEY`). Если у пользователя выставлен этот флаг в
`context.user_data`, входящий текст трактуется как факт для памяти и
сохраняется через `save_memory_record_from_text()` — до `ProcessUserMessage`,
который в этом случае вообще не вызывается.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.application.memory.use_cases.create_memory_record import CreateMemoryRecordUseCase
from dekoder.presentation.telegram.handlers.memory import PENDING_REMEMBER_KEY, save_memory_record_from_text
from dekoder.presentation.telegram.mapper import split_message, to_command
from dekoder.shared.errors import DekoderError
from dekoder.shared.logging import bind_request_context, clear_request_context, get_logger

_logger = get_logger(__name__)

UNEXPECTED_ERROR_MESSAGE = "Произошла непредвиденная ошибка. Попробуйте ещё раз чуть позже."


class TextMessageHandler:
    def __init__(
        self, process_user_message: ProcessUserMessage, create_memory_record: CreateMemoryRecordUseCase
    ) -> None:
        self._process_user_message = process_user_message
        self._create_memory_record = create_memory_record

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None or message.text is None:
            return

        user_data = context.user_data
        # isinstance, не `is not None` — в реальном python-telegram-bot
        # `user_data` либо `dict`, либо `None`, но тесты этого модуля и
        # многих e2e-сценариев передают `context=MagicMock()`: `MagicMock().
        # user_data.pop(...)` сам по себе truthy `MagicMock`, `is not None`
        # ложно сработал бы на каждом обычном сообщении в тех тестах.
        if isinstance(user_data, dict) and user_data.pop(PENDING_REMEMBER_KEY, False):
            await save_memory_record_from_text(self._create_memory_record, update, message, message.text.strip())
            return

        command = to_command(update)
        bind_request_context(correlation_id=command.correlation_id)
        try:
            result = await self._process_user_message.execute(command)
            # Sprint 4, задача S4-07 (ADR-4.6, «дополнительный механизм»):
            # версии использованных шаблонов промпта — для операционной
            # трассируемости («ассистент забыл, что я говорил раньше» —
            # ADR-4.5), внутри области `bind_request_context` (тот же
            # `correlation_id`, что и остальные логи этого запроса) — до
            # `clear_request_context()` в `finally` ниже. Основной,
            # проверяемый тестом механизм — `result.prompt_template_versions`
            # (DTO use case'а), это лишь дополнение.
            #
            # Sprint 9, задача S9-06 (ADR-9.6): агрегированное событие
            # уровня «запрос обработан» — вместе с `process_user_message_failed`
            # (путь неудачи, не переименован) даёт все метрики §17.7
            # (количество запросов/ошибок, среднее время ответа) простым
            # агрегированием по имени события. Значения берутся из уже
            # вычисленного `ProcessUserMessageResult`, не пересчитываются.
            _logger.info(
                "message_processing_completed",
                template_versions=dict(result.prompt_template_versions),
                provider=result.provider_id.value,
                model=result.model_id.value,
                duration_ms=round(result.duration_ms, 1),
                input_tokens=result.usage.input_tokens if result.usage else None,
                output_tokens=result.usage.output_tokens if result.usage else None,
                status="success",
            )
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
