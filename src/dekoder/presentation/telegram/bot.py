"""
Telegram driving adapter — регистрирует `/start` и обработчик текстовых
сообщений поверх уже собранного `ProcessUserMessage`. `ProcessUserMessage`
передаётся параметром (dependency injection из bootstrap-слоя) — этот
модуль не создаёт use case, не создаёт `AsyncSession`/репозитории и не
импортирует `OpenAiCompatibleLLMAdapter`.

Только сборка `telegram.ext.Application` с обработчиками — запуск
(polling/webhook) остаётся вне объёма этой задачи (Docker/деплой).

Sprint 2 (задача S2-06): `build_telegram_application()` и регистрация
обработчика текстовых сообщений разделены на две функции —
`build_telegram_application(bot_token)` (только `/start`, не требует
`ProcessUserMessage`) и `register_message_handler(application,
process_user_message)`. Причина — `telegram_main.py`: с S2-06
`ProcessUserMessage` зависит от `ConversationRepositoriesFactory`, которая
может быть собрана только после инициализации БД
(`bootstrap/database.py::init_database`), а инициализация БД должна
происходить внутри `post_init` `Application.run_polling()` — в event
loop'е, которому будут принадлежать соединения `aiosqlite` (см.
`telegram_main.py`). До S2-06 весь `Application` собирался одной функцией
до `run_polling()`; теперь обработчик текстовых сообщений регистрируется
отдельно, уже внутри `post_init`, когда `ProcessUserMessage` готов.

Sprint 2 (задача S2-08): по той же причине (event loop/БД) команда `/new`
регистрируется отдельной функцией `register_new_conversation_handler`,
тоже вызываемой внутри `post_init`, когда `StartNewConversation` уже
собран контейнером — не в `build_telegram_application()`, как `/start`,
которая не требует БД.

Sprint 2 (задача S2-10): по той же причине команда `/clear`
регистрируется отдельной функцией `register_clear_conversation_handler`,
тоже вызываемой внутри `post_init`, поверх уже собранного
`ClearConversation`.

Sprint 3 (задача S3-08): по той же причине команда `/profile`
(`/profile` + callback выбора профиля) регистрируется отдельной функцией
`register_profile_handlers`, тоже вызываемой внутри `post_init`, поверх
уже собранных `ListProfiles`/`GetActiveProfile`/`SelectProfile`. Первое
использование `CallbackQueryHandler` в проекте — регистрируется с
`pattern=r"^profile:"`, чтобы не перехватывать callback'и других
возможных будущих inline-клавиатур.

Sprint 5 (задача S5-07): по той же причине команды `/remember`/`/memory`
(+ callback удаления записи памяти) регистрируются отдельной функцией
`register_memory_handlers`, тоже вызываемой внутри `post_init`, поверх
уже собранных `CreateMemoryRecordUseCase`/`ListMemoryRecordsUseCase`/
`DeleteMemoryRecordUseCase`. Callback памяти регистрируется с
`pattern=r"^memory_delete:"` — по тому же принципу, что и
`pattern=r"^profile:"`, не перехватывает callback выбора профиля и
наоборот.

Sprint 7 (задача S7-07, ADR-7.9): по той же причине команда `/model`
(+ callback выбора модели) регистрируется отдельной функцией
`register_model_handlers`, тоже вызываемой внутри `post_init`, поверх
уже собранных `ListAvailableModels`/`GetSelectedModel`/`SelectModel`.
Callback выбора модели регистрируется с `pattern=r"^model:"` — дизъюнктен
с уже занятыми `pattern=r"^profile:"`/`pattern=r"^memory_delete:"`.

Sprint 13: `/start` перестаёт быть исключением, не зависящим от БД — теперь
тоже проверяет долговременную память (известно ли имя пользователя,
`ListMemoryRecordsUseCase`, `handlers/start.py::StartCommandHandler`),
поэтому по той же причине (event loop/БД) регистрируется отдельной
функцией `register_start_handler`, тоже вызываемой внутри `post_init` —
не в `build_telegram_application()`, как было до этого спринта.
"""

from __future__ import annotations

from telegram import BotCommand
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from dekoder.application.conversation.use_cases.clear_conversation import ClearConversation
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.application.conversation.use_cases.start_new_conversation import StartNewConversation
from dekoder.application.memory.use_cases.create_memory_record import CreateMemoryRecordUseCase
from dekoder.application.memory.use_cases.delete_memory_record import DeleteMemoryRecordUseCase
from dekoder.application.memory.use_cases.list_memory_records import ListMemoryRecordsUseCase
from dekoder.application.model_catalog.use_cases.get_selected_model import GetSelectedModel
from dekoder.application.model_catalog.use_cases.list_models import ListAvailableModels
from dekoder.application.model_catalog.use_cases.select_model import SelectModel
from dekoder.application.profile.use_cases.get_active_profile import GetActiveProfile
from dekoder.application.profile.use_cases.list_profiles import ListProfiles
from dekoder.application.profile.use_cases.select_profile import SelectProfile
from dekoder.presentation.telegram.handlers.clear_conversation import ClearConversationHandler
from dekoder.presentation.telegram.handlers.memory import (
    MemoryDeleteCallbackHandler,
    MemoryListCommandHandler,
    RememberCommandHandler,
)
from dekoder.presentation.telegram.handlers.messages import TextMessageHandler
from dekoder.presentation.telegram.handlers.model import ModelCommandHandler, ModelSelectionCallbackHandler
from dekoder.presentation.telegram.handlers.new_conversation import NewConversationHandler
from dekoder.presentation.telegram.handlers.profile import ProfileCommandHandler, ProfileSelectionCallbackHandler
from dekoder.presentation.telegram.handlers.start import StartCommandHandler


def build_telegram_application(bot_token: str, proxy_url: str | None = None) -> Application:
    """
    Собирает `Application` без обработчиков — все команды (включая `/start`, Sprint 13) регистрируются отдельно.

    python-telegram-bot по умолчанию даёт connect/read_timeout=5с — недостаточно
    на нестабильном сетевом пути до api.telegram.org, приводит к TimedOut даже
    на успешно обработанных командах (ответ готов, но не успевает уйти).
    proxy_url — TelegramSettings.proxy_url (TELEGRAM_PROXY_URL), нужен только
    когда сеть развёртывания не имеет прямого доступа к Telegram.

    Критично: `telegram.Bot` держит ДВА независимых HTTP-клиента —
    `request` (обычные вызовы: sendMessage, getMe и т.д.) и отдельный
    `get_updates_request` (только для long-polling `getUpdates`). Если
    передать прокси только в `.request(...)`, как было раньше,
    `ApplicationBuilder`/`Bot` молча создают `get_updates_request` со
    значениями по умолчанию — БЕЗ прокси и с read_timeout=5с. Именно
    этот клиент отвечает за приём входящих сообщений (`run_polling()`);
    он пытался идти к Telegram напрямую, что на сети некоторых
    развёртываний блокируется — бот выглядел «живым» (обычные вызовы
    через `request` с прокси работали), но не получал ни одного
    сообщения, стабильно падая по TimedOut ровно на ~5с. Обнаружено и
    подтверждено вживую на проде 2026-09-04 — до этой правки баг
    маскировался под «нестабильность сетевого туннеля».
    `connection_pool_size=1` — как в дефолтном `get_updates_request`
    самого PTB (одно долгоживущее соединение, не пул).
    """
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0, proxy=proxy_url)
    get_updates_request = HTTPXRequest(connection_pool_size=1, connect_timeout=30.0, read_timeout=30.0, proxy=proxy_url)
    return ApplicationBuilder().token(bot_token).request(request).get_updates_request(get_updates_request).build()


def register_start_handler(application: Application, list_memory_records: ListMemoryRecordsUseCase) -> None:
    """Регистрирует команду `/start` поверх уже собранного `ListMemoryRecordsUseCase` (Sprint 13)."""
    application.add_handler(CommandHandler("start", StartCommandHandler(list_memory_records)))


def register_message_handler(
    application: Application,
    process_user_message: ProcessUserMessage,
    create_memory_record: CreateMemoryRecordUseCase,
    get_active_profile: GetActiveProfile,
) -> None:
    """
    Регистрирует обработчик обычных текстовых сообщений поверх уже собранного
    `ProcessUserMessage`. `create_memory_record` (Sprint 12) — завершает
    двухшаговый `/remember` без аргумента, см. докстринг `TextMessageHandler`.
    `get_active_profile` — тот же use case, что и `register_profile_handlers`
    (не отдельный экземпляр контейнера), нужен только для подсказки о
    дальнейших действиях после завершения знакомства (`/start`).
    """
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            TextMessageHandler(process_user_message, create_memory_record, get_active_profile),
        )
    )


def register_new_conversation_handler(application: Application, start_new_conversation: StartNewConversation) -> None:
    """Регистрирует обработчик команды `/new` поверх уже собранного `StartNewConversation`."""
    application.add_handler(CommandHandler("new", NewConversationHandler(start_new_conversation)))


def register_clear_conversation_handler(application: Application, clear_conversation: ClearConversation) -> None:
    """Регистрирует обработчик команды `/clear` поверх уже собранного `ClearConversation`."""
    application.add_handler(CommandHandler("clear", ClearConversationHandler(clear_conversation)))


def register_profile_handlers(
    application: Application,
    list_profiles: ListProfiles,
    get_active_profile: GetActiveProfile,
    select_profile: SelectProfile,
) -> None:
    """Регистрирует команду `/profile` и callback выбора профиля поверх уже собранных use case'ов."""
    application.add_handler(CommandHandler("profile", ProfileCommandHandler(list_profiles, get_active_profile)))
    application.add_handler(CallbackQueryHandler(ProfileSelectionCallbackHandler(select_profile), pattern=r"^profile:"))


def register_memory_handlers(
    application: Application,
    create_memory_record: CreateMemoryRecordUseCase,
    list_memory_records: ListMemoryRecordsUseCase,
    delete_memory_record: DeleteMemoryRecordUseCase,
) -> None:
    """
    Регистрирует команды `/remember`/`/memory` и callback удаления записи
    памяти поверх уже собранных use case'ов памяти. Нет команды `/forget`
    (ADR-5.10) — удаление только через inline-кнопку `MemoryDeleteCallbackHandler`.
    """
    application.add_handler(CommandHandler("remember", RememberCommandHandler(create_memory_record)))
    application.add_handler(CommandHandler("memory", MemoryListCommandHandler(list_memory_records)))
    application.add_handler(
        CallbackQueryHandler(
            MemoryDeleteCallbackHandler(delete_memory_record, list_memory_records),
            pattern=r"^memory_delete:",
        )
    )


def register_model_handlers(
    application: Application,
    list_available_models: ListAvailableModels,
    get_selected_model: GetSelectedModel,
    select_model: SelectModel,
) -> None:
    """Регистрирует команду `/model` и callback выбора модели поверх уже собранных use case'ов (ADR-7.9)."""
    application.add_handler(CommandHandler("model", ModelCommandHandler(list_available_models, get_selected_model)))
    application.add_handler(
        CallbackQueryHandler(ModelSelectionCallbackHandler(select_model, list_available_models), pattern=r"^model:")
    )


_BOT_COMMANDS = (
    BotCommand("start", "Начать работу с ботом"),
    BotCommand("new", "Начать новый диалог"),
    BotCommand("clear", "Очистить историю текущего диалога"),
    BotCommand("profile", "Выбрать профиль ассистента"),
    BotCommand("model", "Выбрать AI-модель"),
    BotCommand("remember", "Сохранить факт в долговременную память"),
    BotCommand("memory", "Показать сохранённые факты памяти"),
)


async def set_bot_commands(application: Application) -> None:
    """Регистрирует список команд в Telegram (меню "/" в клиенте) — только подсказка UI, не влияет на обработку."""
    await application.bot.set_my_commands(list(_BOT_COMMANDS))
