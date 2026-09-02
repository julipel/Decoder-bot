"""
Обработчик команды `/start` (Sprint 13) — знакомится с пользователем: если
имя ещё не известно, показывает список возможностей и просит представиться;
имя, присланное следующим сообщением, сохраняется как запись долговременной
памяти (категория `PERSONAL`) через тот же `save_memory_record_from_text()`,
которым пользуется `/remember` (`handlers/memory.py`) — единая точка
аудит-лога/обработки ошибок, не дублируется здесь. Повторный `/start` уже
знакомого пользователя приветствует по имени и не спрашивает его снова.

Как и остальные хендлеры, которым нужна БД (`/new`, `/clear`, `/profile`,
`/remember`, `/memory`, `/model`), регистрируется не в
`build_telegram_application()`, а отдельной функцией
`register_start_handler()` внутри `post_init` (`bot.py`/`telegram_main.py`)
— до Sprint 13 `/start` был единственным исключением, не зависящим от БД;
теперь зависит (проверка известного имени через `ListMemoryRecordsUseCase`).

Обнаружение уже сохранённого имени — по префиксу `NAME_FACT_PREFIX` в
тексте confirmed-записи категории `PERSONAL`; отдельного поля/схемы «имя
пользователя» в домене памяти нет и не оправдано (claude.md §29, YAGNI) —
та же свободнотекстовая модель, что и любой другой факт `/remember`.
"""

from __future__ import annotations

from collections.abc import Sequence

from telegram import Message, Update
from telegram.ext import ContextTypes

from dekoder.application.memory.use_cases.create_memory_record import CreateMemoryRecordUseCase
from dekoder.application.memory.use_cases.list_memory_records import ListMemoryRecordsUseCase
from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import MemoryCategory
from dekoder.presentation.telegram.handlers.memory import save_memory_record_from_text
from dekoder.presentation.telegram.mapper import to_list_memory_records_command
from dekoder.shared.errors import DekoderError
from dekoder.shared.logging import bind_request_context, clear_request_context, get_logger

_logger = get_logger(__name__)

CAPABILITIES_MESSAGE = (
    "Здравствуйте! Я — персональный AI-ассистент «Декодер».\n"
    "Отправьте мне текстовый запрос, и я постараюсь помочь.\n\n"
    "Что я умею:\n"
    "— запоминаю важные факты о вас и учитываю их в ответах (/remember, /memory);\n"
    "— ищу нужное в загруженной базе знаний и подмешиваю в ответ — без отдельной команды;\n"
    "— работаю в разных профилях-персонах (/profile) и с разными AI-моделями (/model);\n"
    "— веду историю диалога (/new — начать новый, /clear — очистить текущий)."
)
ASK_NAME_MESSAGE = "Как я могу к вам обращаться?"
FIRST_TIME_GREETING = f"{CAPABILITIES_MESSAGE}\n\n{ASK_NAME_MESSAGE}"
RETURNING_GREETING_TEMPLATE = "С возвращением, {name}!\n\n" + CAPABILITIES_MESSAGE
NAME_SAVED_TEMPLATE = "Приятно познакомиться, {name}! Буду обращаться к вам так."

# Ключ в context.user_data — тот же принцип, что PENDING_REMEMBER_KEY
# (handlers/memory.py): выставляется StartCommandHandler, читается и
# снимается TextMessageHandler (presentation/telegram/handlers/messages.py).
PENDING_NAME_KEY = "awaiting_display_name"

# Метка, по которой факт об имени отличается среди PERSONAL-записей памяти
# при следующем /start — обычный текстовый префикс, не сериализация.
NAME_FACT_PREFIX = "Обращение к пользователю: "


def _format_name_fact(name: str) -> str:
    return f"{NAME_FACT_PREFIX}{name}"


def _extract_known_name(records: Sequence[MemoryRecord]) -> str | None:
    for record in records:
        if record.category is MemoryCategory.PERSONAL and record.text.startswith(NAME_FACT_PREFIX):
            return record.text[len(NAME_FACT_PREFIX) :].strip()
    return None


class StartCommandHandler:
    def __init__(self, list_memory_records: ListMemoryRecordsUseCase) -> None:
        self._list_memory_records = list_memory_records

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if message is None:
            return

        known_name = await self._find_known_name(update)
        if known_name is not None:
            await message.reply_text(RETURNING_GREETING_TEMPLATE.format(name=known_name))
            return

        if context.user_data is not None:
            context.user_data[PENDING_NAME_KEY] = True
        await message.reply_text(FIRST_TIME_GREETING)

    async def _find_known_name(self, update: Update) -> str | None:
        try:
            command = to_list_memory_records_command(update)
        except ValueError:
            return None

        bind_request_context(correlation_id=command.correlation_id)
        try:
            result = await self._list_memory_records.execute(command)
        except DekoderError as error:
            # Не блокирует /start — при сбое чтения памяти просто
            # спрашиваем имя заново, тот же принцип устойчивости, что и
            # RAG/qdrant при старте (bootstrap/database.py::init_database
            # — единственное действительно fail-fast чтение в проекте).
            _logger.warning("start_list_memory_records_failed", error_code=error.code)
            return None
        except Exception:
            _logger.exception("start_list_memory_records_unexpected_error")
            return None
        finally:
            clear_request_context()

        return _extract_known_name(result.records)


async def save_display_name_from_text(
    create_memory_record: CreateMemoryRecordUseCase,
    update: Update,
    message: Message,
    raw_name: str,
) -> None:
    """Завершает знакомство: сохраняет имя как `PERSONAL`-факт памяти (см. `TextMessageHandler`/`PENDING_NAME_KEY`)."""
    name = raw_name.strip()
    await save_memory_record_from_text(
        create_memory_record,
        update,
        message,
        _format_name_fact(name),
        category=MemoryCategory.PERSONAL,
        success_message=NAME_SAVED_TEMPLATE.format(name=name),
    )
