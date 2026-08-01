"""
Точка входа второго процесса — Telegram polling (`python -m
dekoder.telegram_main`), запускается отдельным контейнером
(`telegram-bot`) из того же образа, что и ASGI-процесс `main.py`.

Тонкая обёртка над bootstrap-слоем, как и `main.py`: не содержит
конфигурации и не знает деталей сборки контейнера зависимостей —
`Settings()` создаётся один раз, здесь же.

`Application.run_polling()` (python-telegram-bot) сам управляет своим
event loop'ом и уже устанавливает обработчики SIGINT/SIGTERM/SIGABRT
для корректной остановки polling — то, что нужно `docker compose stop`/
`down` (требование «проверь корректное завершение Telegram polling»).

С задачи S2-01 постоянное хранилище данных (`bootstrap/database.py::
init_database`) инициализируется и проверяется внутри `post_init`, а не
до `run_polling()`: `run_polling()` создаёт собственный event loop, а
соединения `aiosqlite` привязаны к тому loop'у, в котором были открыты —
инициализация вне `post_init` создала бы `AsyncEngine` в чужом,
временном loop'е. Ошибка подключения к базе данных внутри `post_init`
останавливает запуск процесса (`Application.__run` пробрасывает
исключение из `post_init` дальше, после штатной попытки завершения) —
то же fail-fast поведение, что и в `bootstrap/application.py`.

С задачи S2-06 по той же причине (event loop) внутри `post_init`
собирается и весь `ApplicationContainer` (`build_container()`), а не
только `AsyncEngine`/фабрика сессий: `ProcessUserMessage` теперь зависит
от `ConversationRepositoriesFactory`, построенной поверх
`db_session_factory`, которая должна принадлежать loop'у `run_polling()`.
Поэтому обработчик текстовых сообщений (`presentation/telegram/bot.py::
register_message_handler`) регистрируется тоже внутри `post_init`, уже
после того как `container.process_user_message` готов — `/start` не
зависит от БД и регистрируется заранее, как и раньше, через
`build_telegram_application()`.

С задачи S2-08 по той же причине обработчик команды `/new`
(`presentation/telegram/bot.py::register_new_conversation_handler`)
регистрируется тоже внутри `post_init`, сразу после обработчика
текстовых сообщений, поверх уже собранного `container.start_new_conversation`.

С задачи S2-10 по той же причине обработчик команды `/clear`
(`presentation/telegram/bot.py::register_clear_conversation_handler`)
регистрируется тоже внутри `post_init`, сразу после обработчика команды
`/new`, поверх уже собранного `container.clear_conversation`.
"""

from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine
from telegram.ext import Application

from dekoder.bootstrap.container import build_container
from dekoder.bootstrap.database import dispose_database, init_database
from dekoder.presentation.telegram.bot import (
    build_telegram_application,
    register_clear_conversation_handler,
    register_message_handler,
    register_new_conversation_handler,
)
from dekoder.shared.config import Settings
from dekoder.shared.logging import configure_logging, get_logger

_logger = get_logger(__name__)


def main() -> None:
    settings = Settings()
    configure_logging(
        environment=settings.application.environment,
        level="DEBUG" if settings.application.debug else "INFO",
    )

    http_client = httpx.AsyncClient(
        base_url=settings.openrouter.base_url,
        timeout=settings.llm.timeout,
    )
    application = build_telegram_application(bot_token=settings.telegram.bot_token.get_secret_value())

    # Заполняется внутри `_startup`, читается внутри `_shutdown` — оба
    # колбэка выполняются в одном и том же loop'е `run_polling()`, простая
    # изменяемая ссылка достаточна и не требует глобального состояния
    # модуля (движок нигде не хранится за пределами этой функции).
    db_engine_holder: dict[str, AsyncEngine] = {}

    async def _startup(app: Application) -> None:
        # post_init вызывается после успешной Application.initialize()
        # (в т.ч. getMe) — если этот лог не появился, polling не начался.
        _logger.info("telegram_polling_started")
        db_engine, db_session_factory = await init_database(settings)
        db_engine_holder["engine"] = db_engine

        container = build_container(settings, http_client, db_session_factory)
        register_message_handler(app, container.process_user_message)
        register_new_conversation_handler(app, container.start_new_conversation)
        register_clear_conversation_handler(app, container.clear_conversation)

    async def _shutdown(_: Application) -> None:
        # Вызывается run_polling() при штатной остановке (после
        # обработки SIGINT/SIGTERM) — здесь http_client и AsyncEngine
        # реально закрываются.
        _logger.info("telegram_polling_stopping")
        await http_client.aclose()
        db_engine = db_engine_holder.get("engine")
        if db_engine is not None:
            await dispose_database(db_engine)

    application.post_init = _startup
    application.post_shutdown = _shutdown
    application.run_polling()


if __name__ == "__main__":
    main()
