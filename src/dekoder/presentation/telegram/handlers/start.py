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

`NAME_FACT_PREFIX`/`format_display_name_fact`/`extract_display_name`
переехали в `application/memory/display_name.py` — этой же логикой
теперь пользуется и `ProcessUserMessage` (обращение по имени в каждом
ответе), а presentation не может быть зависимостью application-слоя
(claude.md §6). Здесь оставлены только реэкспорт-импорты, чтобы не
трогать существующие вызовы/тесты этого модуля.

После успешного сохранения имени `save_display_name_from_text` присылает
второе сообщение — краткую подсказку о дальнейших действиях (профиль,
модель или обычное сообщение), с именем реально активного профиля
(`GetActiveProfile`, тот же use case, что и у `/profile`) — не хардкод
названия профиля по умолчанию, т.к. персональный выбор мог быть сделан
раньше (в теории — на практике невозможно раньше первого `/start`, но
`GetActiveProfile` — уже существующий безусловный источник истины, не
дублируется отдельным чтением каталога).
"""

from __future__ import annotations

from telegram import Message, Update
from telegram.ext import ContextTypes

from dekoder.application.memory.display_name import (
    NAME_FACT_PREFIX,
    extract_display_name,
    format_display_name_fact,
)
from dekoder.application.memory.use_cases.create_memory_record import CreateMemoryRecordUseCase
from dekoder.application.memory.use_cases.list_memory_records import ListMemoryRecordsUseCase
from dekoder.application.profile.use_cases.get_active_profile import GetActiveProfile
from dekoder.domain.memory.value_objects import MemoryCategory
from dekoder.presentation.telegram.handlers.memory import save_memory_record_from_text
from dekoder.presentation.telegram.mapper import to_get_active_profile_command, to_list_memory_records_command
from dekoder.shared.errors import DekoderError
from dekoder.shared.logging import bind_request_context, clear_request_context, get_logger

_logger = get_logger(__name__)

__all__ = ["NAME_FACT_PREFIX", "StartCommandHandler", "save_display_name_from_text"]

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
NEXT_STEPS_HINT_TEMPLATE = (
    "Чтобы продолжить, вы можете выбрать профиль (/profile), выбрать модель (/model) "
    "или просто написать сообщение — и я отвечу. Сейчас включён профиль «{profile_name}»."
)
NEXT_STEPS_HINT_FALLBACK = (
    "Чтобы продолжить, вы можете выбрать профиль (/profile), выбрать модель (/model) "
    "или просто написать сообщение — и я отвечу."
)

# Ключ в context.user_data — тот же принцип, что PENDING_REMEMBER_KEY
# (handlers/memory.py): выставляется StartCommandHandler, читается и
# снимается TextMessageHandler (presentation/telegram/handlers/messages.py).
PENDING_NAME_KEY = "awaiting_display_name"


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

        return extract_display_name(result.records)


async def save_display_name_from_text(
    create_memory_record: CreateMemoryRecordUseCase,
    get_active_profile: GetActiveProfile,
    update: Update,
    message: Message,
    raw_name: str,
) -> None:
    """
    Завершает знакомство: сохраняет имя как `PERSONAL`-факт памяти (см.
    `TextMessageHandler`/`PENDING_NAME_KEY`), затем — только если факт
    реально сохранён, не после сообщения об ошибке — присылает вторым
    сообщением подсказку о дальнейших действиях.
    """
    name = raw_name.strip()
    saved = await save_memory_record_from_text(
        create_memory_record,
        update,
        message,
        format_display_name_fact(name),
        category=MemoryCategory.PERSONAL,
        success_message=NAME_SAVED_TEMPLATE.format(name=name),
    )
    if saved:
        await message.reply_text(await _build_next_steps_hint(get_active_profile, update))


async def _build_next_steps_hint(get_active_profile: GetActiveProfile, update: Update) -> str:
    """
    Имя активного профиля — не хардкод: пользователь только что создан
    (`save_memory_record_from_text` уже вызвал `get_or_create_by_telegram_user_id`),
    `GetActiveProfile` вернёт профиль с `is_default=True` (тот же путь,
    что и `/profile`). Сбой этого чтения не должен ломать знакомство —
    та же устойчивость, что и `StartCommandHandler._find_known_name`:
    при ошибке просто отправляется подсказка без названия профиля.
    """
    try:
        command = to_get_active_profile_command(update)
    except ValueError:
        return NEXT_STEPS_HINT_FALLBACK

    bind_request_context(correlation_id=command.correlation_id)
    try:
        result = await get_active_profile.execute(command)
    except DekoderError as error:
        _logger.warning("start_get_active_profile_failed", error_code=error.code)
        return NEXT_STEPS_HINT_FALLBACK
    except Exception:
        _logger.exception("start_get_active_profile_unexpected_error")
        return NEXT_STEPS_HINT_FALLBACK
    finally:
        clear_request_context()

    if result.profile is None:
        return NEXT_STEPS_HINT_FALLBACK
    return NEXT_STEPS_HINT_TEMPLATE.format(profile_name=result.profile.name)
