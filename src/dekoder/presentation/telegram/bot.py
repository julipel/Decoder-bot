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
"""

from __future__ import annotations

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

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
from dekoder.presentation.telegram.handlers.start import handle_start


def build_telegram_application(bot_token: str) -> Application:
    """Собирает `Application` и регистрирует `/start` — обработчики текста и `/new` добавляются отдельно."""
    application = ApplicationBuilder().token(bot_token).build()
    application.add_handler(CommandHandler("start", handle_start))
    return application


def register_message_handler(application: Application, process_user_message: ProcessUserMessage) -> None:
    """Регистрирует обработчик обычных текстовых сообщений поверх уже собранного `ProcessUserMessage`."""
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, TextMessageHandler(process_user_message)))


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
