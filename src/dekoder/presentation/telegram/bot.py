"""
Telegram driving adapter — регистрирует `/start` и обработчик текстовых
сообщений поверх уже собранного `ProcessUserMessage`. `ProcessUserMessage`
передаётся параметром (dependency injection из bootstrap-слоя) — этот
модуль не создаёт use case, не создаёт `AsyncSession`/репозитории и не
импортирует `OpenRouterLLMAdapter`.

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
"""

from __future__ import annotations

from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters

from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.application.conversation.use_cases.start_new_conversation import StartNewConversation
from dekoder.presentation.telegram.handlers.messages import TextMessageHandler
from dekoder.presentation.telegram.handlers.new_conversation import NewConversationHandler
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
