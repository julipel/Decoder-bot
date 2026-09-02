"""
Обработчики команд `/remember`/`/memory` — единственное место в
presentation-слое, вызывающее `CreateMemoryRecordUseCase`/
`ListMemoryRecordsUseCase`/`DeleteMemoryRecordUseCase` (Sprint 5, задача
S5-07).

Получают use case'ы через конструктор (dependency injection, тот же
стиль, что и `ClearConversationHandler`/`ProfileCommandHandler`) — не
работают с SQLAlchemy, ORM-моделями или репозиториями напрямую.

Три обработчика:
- `RememberCommandHandler` — `CommandHandler("remember", ...)`, извлекает
  текст после команды, вызывает `CreateMemoryRecordUseCase` (`mapper.py::
  to_create_memory_record_command` — `status=CONFIRMED, source=
  USER_EXPLICIT`, ADR-5.9); `/remember` без текста не показывает ошибку, а
  просит написать факт следующим сообщением и выставляет
  `context.user_data[PENDING_REMEMBER_KEY] = True` — обычный текстовый
  обработчик (`presentation/telegram/handlers/messages.py::
  TextMessageHandler`) проверяет этот флаг раньше, чем передавать текст в
  `ProcessUserMessage`, и при совпадении сохраняет факт тем же
  `save_memory_record_from_text()`, которым пользуется и сам
  `RememberCommandHandler` (Sprint 12) — единственная точка сохранения, не
  дублирует логику аудит-лога/обработки ошибок;
- `MemoryListCommandHandler` — `CommandHandler("memory", ...)`, вызывает
  `ListMemoryRecordsUseCase`, строит `InlineKeyboardMarkup` с кнопкой 🗑
  на каждую запись; пустой список — дружелюбное сообщение, не пустая
  клавиатура;
- `MemoryDeleteCallbackHandler` — `CallbackQueryHandler`, разбирает
  `callback_data` (`memory_delete:<uuid>`), вызывает
  `DeleteMemoryRecordUseCase` с `telegram_user_id` из `update.
  callback_query.from_user` (НЕ `update.effective_user`, ADR-5.10), затем
  `query.answer()` + `query.edit_message_text(...)` с обновлённым
  списком — тот же стиль, что и `ProfileSelectionCallbackHandler`.

Нет команды `/forget` (ADR-5.10) — удаление только через inline-кнопку.

`callback_data` кодирует только `record_id` (`f"memory_delete:{record.id}"`,
`_build_memory_keyboard`/`_parse_memory_delete_callback_data`) — не
сериализует запись целиком.

`DekoderError` → `error.user_message`; любое другое исключение →
нейтральное сообщение + `_logger.exception`, без утечки внутренних
деталей пользователю — тот же принцип, что и у остальных обработчиков.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from dekoder.application.memory.dto import ListMemoryRecordsCommand
from dekoder.application.memory.use_cases.create_memory_record import CreateMemoryRecordUseCase
from dekoder.application.memory.use_cases.delete_memory_record import DeleteMemoryRecordUseCase
from dekoder.application.memory.use_cases.list_memory_records import ListMemoryRecordsUseCase
from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import MemoryCategory
from dekoder.presentation.telegram.mapper import (
    to_create_memory_record_command,
    to_delete_memory_record_command,
    to_list_memory_records_command,
)
from dekoder.shared.errors import DekoderError
from dekoder.shared.logging import bind_request_context, clear_request_context, get_logger, log_audit_event

_logger = get_logger(__name__)

REMEMBER_PROMPT_MESSAGE = "Напишите, что запомнить, следующим сообщением."
REMEMBER_SAVED_MESSAGE = "Запомнил."
MEMORY_EMPTY_MESSAGE = "У вас пока нет сохранённых фактов. Используйте /remember <текст>, чтобы сохранить факт."
MEMORY_LIST_HEADER = "Ваши сохранённые факты (нажмите 🗑, чтобы удалить):"
UNEXPECTED_ERROR_MESSAGE = "Произошла непредвиденная ошибка. Попробуйте ещё раз чуть позже."

# Ключ в context.user_data — выставляется RememberCommandHandler, читается и
# снимается TextMessageHandler (Sprint 12): следующее обычное текстовое
# сообщение этого пользователя трактуется как текст факта, не как реплика в
# ProcessUserMessage.
PENDING_REMEMBER_KEY = "awaiting_remember_text"

_CALLBACK_DATA_PREFIX = "memory_delete:"
_DELETE_BUTTON_LABEL = "🗑"


def _extract_remember_argument(message_text: str) -> str:
    """
    Разбирает `"/remember <текст>"` (в т.ч. `"/remember@bot_name <текст>"`
    — `python-telegram-bot` не отрезает упоминание бота из `message.text`
    сам). `maxsplit=1` — сохраняет внутренние пробелы/переносы строк
    текста факта как есть, не схлопывает их (в отличие от
    `context.args`, который `python-telegram-bot` собирает разбиением по
    пробелам).
    """
    parts = message_text.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


def _render_memory_list_text(records: Sequence[MemoryRecord]) -> str:
    lines = [MEMORY_LIST_HEADER, ""]
    lines.extend(f"{index}. {record.text}" for index, record in enumerate(records, start=1))
    return "\n".join(lines)


def _build_memory_keyboard(records: Sequence[MemoryRecord]) -> InlineKeyboardMarkup:
    """Одна кнопка 🗑 на запись; порядковый номер в подписи кнопки соответствует номеру строки в тексте списка."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"{_DELETE_BUTTON_LABEL} {index}",
                callback_data=f"{_CALLBACK_DATA_PREFIX}{record.id}",
            )
        ]
        for index, record in enumerate(records, start=1)
    ]
    return InlineKeyboardMarkup(rows)


def _parse_memory_delete_callback_data(data: str) -> UUID | None:
    """Разбирает `callback_data` вида `memory_delete:<uuid>`; `None` — не наш формат или невалидный UUID."""
    if not data.startswith(_CALLBACK_DATA_PREFIX):
        return None
    raw_record_id = data[len(_CALLBACK_DATA_PREFIX) :]
    try:
        return UUID(raw_record_id)
    except ValueError:
        return None


async def save_memory_record_from_text(
    create_memory_record: CreateMemoryRecordUseCase,
    update: Update,
    message: Message,
    text: str,
    *,
    category: MemoryCategory = MemoryCategory.OTHER,
    success_message: str = REMEMBER_SAVED_MESSAGE,
) -> None:
    """
    Общая логика сохранения факта — вызывается `RememberCommandHandler`
    (однострочный `/remember <текст>`), `TextMessageHandler` (текст,
    присланный после `/remember` без аргумента, см. `PENDING_REMEMBER_KEY`)
    и `handlers/start.py::save_display_name_from_text` (имя пользователя,
    введённое после `/start`, Sprint 13) — единственное место,
    формирующее аудит-лог/обработку ошибок для создания записи памяти,
    чтобы все пути не расходились.

    `category`/`success_message` — необязательные параметры (Sprint 13):
    по умолчанию поведение не меняется (`/remember`), но позволяют
    переиспользовать эту же функцию для факта другой категории с другим
    подтверждающим сообщением, не дублируя try/except/аудит-лог.
    """
    try:
        command = to_create_memory_record_command(update, text, category=category)
    except ValueError:
        return

    bind_request_context(correlation_id=command.correlation_id)
    try:
        result = await create_memory_record.execute(command)
    except DekoderError as error:
        _logger.warning("create_memory_record_failed", error_code=error.code)
        await message.reply_text(error.user_message)
        return
    except Exception:
        _logger.exception("create_memory_record_unexpected_error")
        await message.reply_text(UNEXPECTED_ERROR_MESSAGE)
        return
    else:
        log_audit_event(_logger, "memory_record_created", record_id=str(result.record.id))
    finally:
        clear_request_context()

    await message.reply_text(success_message)


class RememberCommandHandler:
    def __init__(self, create_memory_record: CreateMemoryRecordUseCase) -> None:
        self._create_memory_record = create_memory_record

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None or message.text is None:
            return

        argument_text = _extract_remember_argument(message.text)
        if not argument_text:
            if context.user_data is not None:
                context.user_data[PENDING_REMEMBER_KEY] = True
            await message.reply_text(REMEMBER_PROMPT_MESSAGE)
            return

        await save_memory_record_from_text(self._create_memory_record, update, message, argument_text)


class MemoryListCommandHandler:
    def __init__(self, list_memory_records: ListMemoryRecordsUseCase) -> None:
        self._list_memory_records = list_memory_records

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return

        try:
            command = to_list_memory_records_command(update)
        except ValueError:
            return

        bind_request_context(correlation_id=command.correlation_id)
        try:
            result = await self._list_memory_records.execute(command)
        except DekoderError as error:
            _logger.warning("list_memory_records_failed", error_code=error.code)
            await message.reply_text(error.user_message)
            return
        except Exception:
            _logger.exception("list_memory_records_unexpected_error")
            await message.reply_text(UNEXPECTED_ERROR_MESSAGE)
            return
        finally:
            clear_request_context()

        if not result.records:
            await message.reply_text(MEMORY_EMPTY_MESSAGE)
            return

        await message.reply_text(
            _render_memory_list_text(result.records),
            reply_markup=_build_memory_keyboard(result.records),
        )


class MemoryDeleteCallbackHandler:
    def __init__(
        self,
        delete_memory_record: DeleteMemoryRecordUseCase,
        list_memory_records: ListMemoryRecordsUseCase,
    ) -> None:
        self._delete_memory_record = delete_memory_record
        self._list_memory_records = list_memory_records

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None or query.data is None:
            return

        record_id = _parse_memory_delete_callback_data(query.data)
        await query.answer()
        if record_id is None:
            return

        try:
            delete_command = to_delete_memory_record_command(update, record_id)
        except ValueError:
            return

        bind_request_context(correlation_id=delete_command.correlation_id)
        try:
            await self._delete_memory_record.execute(delete_command)
        except DekoderError as error:
            _logger.warning("delete_memory_record_failed", error_code=error.code)
            await query.edit_message_text(error.user_message)
            return
        except Exception:
            _logger.exception("delete_memory_record_unexpected_error")
            await query.edit_message_text(UNEXPECTED_ERROR_MESSAGE)
            return
        else:
            log_audit_event(_logger, "memory_record_deleted", record_id=str(delete_command.record_id))
        finally:
            clear_request_context()

        bind_request_context(correlation_id=delete_command.correlation_id)
        try:
            list_result = await self._list_memory_records.execute(
                ListMemoryRecordsCommand(
                    telegram_user_id=delete_command.telegram_user_id,
                    correlation_id=delete_command.correlation_id,
                )
            )
        except DekoderError as error:
            _logger.warning("list_memory_records_failed", error_code=error.code)
            await query.edit_message_text(error.user_message)
            return
        except Exception:
            _logger.exception("list_memory_records_unexpected_error")
            await query.edit_message_text(UNEXPECTED_ERROR_MESSAGE)
            return
        finally:
            clear_request_context()

        if not list_result.records:
            await query.edit_message_text(MEMORY_EMPTY_MESSAGE)
            return

        await query.edit_message_text(
            _render_memory_list_text(list_result.records),
            reply_markup=_build_memory_keyboard(list_result.records),
        )
