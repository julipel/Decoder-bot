"""
Telegram driving adapter — регистрирует `/start` и обработчик текстовых
сообщений поверх уже собранного `ProcessUserMessage`. `ProcessUserMessage`
передаётся параметром (dependency injection из bootstrap-слоя) — этот
модуль не создаёт use case и не импортирует `OpenRouterLLMAdapter`.

Только сборка `telegram.ext.Application` с обработчиками — запуск
(polling/webhook) остаётся вне объёма этой задачи (Docker/деплой).
"""

from __future__ import annotations

from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters

from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.presentation.telegram.handlers.messages import TextMessageHandler
from dekoder.presentation.telegram.handlers.start import handle_start


def build_telegram_application(bot_token: str, process_user_message: ProcessUserMessage) -> Application:
    application = ApplicationBuilder().token(bot_token).build()

    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, TextMessageHandler(process_user_message)))
    return application
