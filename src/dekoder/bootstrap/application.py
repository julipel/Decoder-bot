"""
create_application — фабрика FastAPI-приложения (bootstrap-слой,
единственное место, которому разрешено знать одновременно про Settings,
конкретные адаптеры и FastAPI).

Жизненный цикл `httpx.AsyncClient` управляется через FastAPI lifespan:
клиент создаётся при старте приложения (внутри `async with` в
`_lifespan`) и закрывается при остановке (выход из `async with`) — не
при импорте модуля и не внутри `OpenRouterLLMAdapter.generate()`.

С задачи S2-01 `_lifespan` также инициализирует постоянное хранилище
данных (`bootstrap/database.py::init_database`) до того, как приложение
начнёт принимать запросы: ошибка подключения к базе данных не даёт
FastAPI завершить запуск (fail-fast), а не проявляется позже как ошибка
первого запроса. `AsyncEngine` создаётся и уничтожается (`dispose()`) в
одном и том же event loop — loop'е uvicorn, обслуживающем `_lifespan`.

С задачи S2-06 `db_session_factory` передаётся в `build_container()` —
`ProcessUserMessage` внутри контейнера получает `ConversationRepositoriesFactory`
(`bootstrap/repositories.py`), поверх которой сам открывает короткие
транзакции. Инициализация БД по-прежнему выполняется до сборки контейнера
внутри одного и того же `_lifespan` (единый event loop uvicorn) — здесь,
в отличие от `telegram_main.py`, нет ограничения на event loop, поэтому
порядок остался прежним.

С задачи S6-08 (Sprint 6) `_lifespan` дополнительно открывает второй
`httpx.AsyncClient` (для `OpenAiEmbeddingProvider`, независимый от
клиента OpenRouter — другой `base_url`, ADR-6.3) и `AsyncQdrantClient`, и
закрывает оба при остановке — тем же `async with`, что и клиент
OpenRouter. В отличие от `init_database`, `ensure_collection` здесь НЕ
fail-fast: RAG — дополнение к базовому диалогу (ADR ProcessUserMessage.
_search_knowledge, тот же принцип), не его предпосылка — недоступность
Qdrant при старте логируется и не мешает приложению принять трафик;
`ProcessUserMessage` в этом случае просто не найдёт коллекцию на каждом
поиске и вернёт пустой RAG-контекст (`_search_knowledge` перехватывает
эту же ошибку и там).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request

from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.bootstrap.container import ApplicationContainer, build_container
from dekoder.bootstrap.database import dispose_database, init_database
from dekoder.composition.health import APP_VERSION
from dekoder.composition.health import router as health_router
from dekoder.infrastructure.qdrant.client import build_qdrant_client, ensure_collection
from dekoder.shared.config import Settings
from dekoder.shared.errors import InfrastructureError
from dekoder.shared.logging import configure_logging, get_logger

_logger = get_logger(__name__)


def create_application(settings: Settings) -> FastAPI:
    configure_logging(
        environment=settings.application.environment,
        level="DEBUG" if settings.application.debug else "INFO",
    )

    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        db_engine, db_session_factory = await init_database(settings)
        qdrant_client = build_qdrant_client(settings.qdrant)
        try:
            try:
                await ensure_collection(qdrant_client, settings.qdrant)
            except InfrastructureError as error:
                # Не fail-fast, в отличие от init_database: RAG — дополнение
                # к базовому диалогу, не его предпосылка (см. докстринг
                # модуля) — приложение продолжает запуск, ProcessUserMessage
                # деградирует до пустого RAG-контекста на каждом поиске.
                _logger.error("qdrant_collection_unavailable_at_startup", error=str(error))
            async with (
                httpx.AsyncClient(
                    base_url=settings.openrouter.base_url,
                    timeout=settings.llm.timeout,
                ) as http_client,
                # timeout переиспользует LLMSettings.timeout — тот же
                # порядок терпимости к внешним генеративным/embedding API,
                # отдельная настройка ради одного значения не оправдана.
                httpx.AsyncClient(
                    base_url=settings.openai.base_url,
                    timeout=settings.llm.timeout,
                ) as openai_http_client,
            ):
                app.state.container = build_container(
                    settings, http_client, openai_http_client, qdrant_client, db_session_factory
                )
                app.state.db_engine = db_engine
                app.state.db_session_factory = db_session_factory
                yield
                # Дошли сюда при остановке приложения: `async with` сейчас
                # выйдет из блока и закроет оба httpx-клиента
                # (httpx.AsyncClient.__aexit__) — единственное место, где
                # они закрываются.
        finally:
            await qdrant_client.close()
            await dispose_database(db_engine)

    app = FastAPI(title=settings.application.name, version=APP_VERSION, lifespan=_lifespan)
    app.include_router(health_router)
    return app


def get_container(request: Request) -> ApplicationContainer:
    """
    FastAPI-зависимость: доступ к контейнеру через `request.app.state`,
    не через глобальную переменную — не service locator (требование 9):
    доступен только тому, кто получил `Request`/`app`, не любому модулю
    на импорте.
    """
    container: ApplicationContainer = request.app.state.container
    return container


def get_process_user_message(request: Request) -> ProcessUserMessage:
    """
    Единственный способ для driving-адаптеров (Telegram и др.) получить
    `ProcessUserMessage` — без импорта `OpenRouterLLMAdapter` напрямую.
    """
    return get_container(request).process_user_message
