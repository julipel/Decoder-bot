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
после того как `container.process_user_message` готов. До Sprint 13
`/start` был исключением (не зависел от БД, регистрировался заранее
через `build_telegram_application()`) — с Sprint 13 тоже зависит
(проверяет память на известное имя пользователя) и регистрируется здесь
же, `register_start_handler`.

С задачи S2-08 по той же причине обработчик команды `/new`
(`presentation/telegram/bot.py::register_new_conversation_handler`)
регистрируется тоже внутри `post_init`, сразу после обработчика
текстовых сообщений, поверх уже собранного `container.start_new_conversation`.

С задачи S2-10 по той же причине обработчик команды `/clear`
(`presentation/telegram/bot.py::register_clear_conversation_handler`)
регистрируется тоже внутри `post_init`, сразу после обработчика команды
`/new`, поверх уже собранного `container.clear_conversation`.

С задачи S3-08 (Sprint 3) по той же причине обработчики команды
`/profile` (`presentation/telegram/bot.py::register_profile_handlers`)
регистрируются тоже внутри `post_init`, сразу после обработчика команды
`/clear`, поверх уже собранных `container.list_profiles`/
`container.get_active_profile`/`container.select_profile`.

С задачи S5-07 (Sprint 5) по той же причине обработчики команд
`/remember`/`/memory` (`presentation/telegram/bot.py::
register_memory_handlers`) регистрируются тоже внутри `post_init`, сразу
после обработчиков `/profile`, поверх уже собранных
`container.create_memory_record`/`container.list_memory_records`/
`container.delete_memory_record`.

С задачи S6-08 (Sprint 6) `post_init` дополнительно открывает второй
`httpx.AsyncClient` (для `OpenAiEmbeddingProvider`, независимый от
клиента LLM-провайдера, ADR-6.3; настройки переименованы и
параметризованы в Sprint 12, ADR-12.1) и `AsyncQdrantClient` до регистрации
обработчиков; оба закрываются в
`_shutdown`. В отличие от `init_database`, `ensure_collection` НЕ
fail-fast (см. `bootstrap/application.py` — тот же принцип для обоих
процессов): RAG — дополнение к диалогу, недоступность Qdrant при старте
логируется, не останавливает polling.

С задачи S7-07 (Sprint 7) по той же причине обработчики команды `/model`
(`presentation/telegram/bot.py::register_model_handlers`) регистрируются
тоже внутри `post_init`, сразу после обработчиков `/remember`/`/memory`,
поверх уже собранных `container.list_available_models`/
`container.get_selected_model`/`container.select_model`.
"""

from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine
from telegram.ext import Application

from dekoder.bootstrap.container import build_container
from dekoder.bootstrap.database import dispose_database, init_database
from dekoder.infrastructure.qdrant.client import build_qdrant_client, ensure_collection
from dekoder.presentation.telegram.bot import (
    build_telegram_application,
    register_clear_conversation_handler,
    register_memory_handlers,
    register_message_handler,
    register_model_handlers,
    register_new_conversation_handler,
    register_profile_handlers,
    register_start_handler,
    set_bot_commands,
)
from dekoder.shared.config import Settings
from dekoder.shared.errors import InfrastructureError
from dekoder.shared.logging import configure_logging, get_logger

_logger = get_logger(__name__)


def main() -> None:
    settings = Settings()
    configure_logging(
        environment=settings.application.environment,
        # APP_DEBUG=true остаётся строго приоритетнее APP_LOG_LEVEL — см.
        # bootstrap/application.py (тот же принцип, отдельная точка вызова
        # для второго процесса, Sprint 11, S11-04, ADR-11.5).
        level="DEBUG" if settings.application.debug else settings.application.log_level,
    )

    http_client = httpx.AsyncClient(
        base_url=settings.llm_provider.base_url,
        timeout=settings.llm.timeout,
    )
    # timeout переиспользует LLMSettings.timeout — см. bootstrap/application.py.
    embedding_http_client = httpx.AsyncClient(
        base_url=settings.embedding_provider.base_url,
        timeout=settings.llm.timeout,
    )
    qdrant_client = build_qdrant_client(settings.qdrant)
    application = build_telegram_application(
        bot_token=settings.telegram.bot_token.get_secret_value(),
        proxy_url=settings.telegram.proxy_url,
    )

    # Заполняется внутри `_startup`, читается внутри `_shutdown` — оба
    # колбэка выполняются в одном и том же loop'е `run_polling()`, простая
    # изменяемая ссылка достаточна и не требует глобального состояния
    # модуля (движок нигде не хранится за пределами этой функции).
    db_engine_holder: dict[str, AsyncEngine] = {}

    async def _startup(app: Application) -> None:
        # post_init вызывается после успешной Application.initialize()
        # (в т.ч. getMe) — если этот лог не появился, polling не начался.
        _logger.info("telegram_polling_started")
        await set_bot_commands(app)
        db_engine, db_session_factory = await init_database(settings)
        db_engine_holder["engine"] = db_engine
        try:
            await ensure_collection(qdrant_client, settings.qdrant)
        except InfrastructureError as error:
            # Не fail-fast — см. докстринг модуля/bootstrap/application.py.
            _logger.error("qdrant_collection_unavailable_at_startup", error=str(error))

        container = build_container(settings, http_client, embedding_http_client, qdrant_client, db_session_factory)
        register_start_handler(app, container.list_memory_records)
        register_message_handler(app, container.process_user_message, container.create_memory_record)
        register_new_conversation_handler(app, container.start_new_conversation)
        register_clear_conversation_handler(app, container.clear_conversation)
        register_profile_handlers(app, container.list_profiles, container.get_active_profile, container.select_profile)
        register_memory_handlers(
            app,
            container.create_memory_record,
            container.list_memory_records,
            container.delete_memory_record,
        )
        register_model_handlers(
            app,
            container.list_available_models,
            container.get_selected_model,
            container.select_model,
        )

    async def _shutdown(_: Application) -> None:
        # Вызывается run_polling() при штатной остановке (после
        # обработки SIGINT/SIGTERM) — здесь http_client и AsyncEngine
        # реально закрываются.
        _logger.info("telegram_polling_stopping")
        await http_client.aclose()
        await embedding_http_client.aclose()
        await qdrant_client.close()
        db_engine = db_engine_holder.get("engine")
        if db_engine is not None:
            await dispose_database(db_engine)

    application.post_init = _startup
    application.post_shutdown = _shutdown
    # bootstrap_retries по умолчанию 0 — единственный неудачный запрос get_me()
    # на нестабильной сети роняет процесс целиком до первого события polling.
    application.run_polling(bootstrap_retries=3)


if __name__ == "__main__":
    main()
