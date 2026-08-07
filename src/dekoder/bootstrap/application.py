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

С задачи S8-03 (Sprint 8, ADR-8.2) `_lifespan` дополнительно публикует на
`app.state` три объекта, которые уже создавались здесь и раньше, но не
были доступны driving-адаптерам за пределами `ApplicationContainer`:
`settings`, `openai_http_client`, `qdrant_client` (`http_client`/
`db_engine`/`db_session_factory`/`container` уже публиковались). Четыре
новые accessor-функции (`get_settings`/`get_db_session_factory`/
`get_openai_http_client`/`get_qdrant_client`) — тот же приём, что уже
существующие `get_container`/`get_process_user_message`: единственный
способ для admin REST-зависимостей (`presentation/api/dependencies/
documents.py`, S8-05) добраться до этих объектов через `Request`, не
через глобальную переменную или собственный service locator.

Также с S8-03 здесь регистрируются глобальные обработчики ошибок
(`presentation/api/error_handlers.py::dekoder_error_handler`/
`unhandled_exception_handler`, ADR-8.12) — единый JSON-конверт ошибок
для всех текущих и будущих REST-роутов. `GET /health` не поднимает
`DekoderError`, поэтому обработчики для него безвредны и ничего не
меняют в его поведении/контракте.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.bootstrap.container import ApplicationContainer, build_container
from dekoder.bootstrap.database import dispose_database, init_database
from dekoder.composition.health import APP_VERSION
from dekoder.composition.health import router as health_router
from dekoder.infrastructure.qdrant.client import build_qdrant_client, ensure_collection
from dekoder.presentation.api.error_handlers import dekoder_error_handler, unhandled_exception_handler
from dekoder.shared.config import Settings
from dekoder.shared.errors import DekoderError, InfrastructureError
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
                app.state.settings = settings
                app.state.openai_http_client = openai_http_client
                app.state.qdrant_client = qdrant_client
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
    # Регистрация admin-роутеров (S8-05, ADR-8.2) — после health_router, не
    # взамен: GET /health остаётся без auth и без изменений в контракте.
    # Импорт роутеров — внутри функции, а не на уровне модуля: их
    # зависимости (`presentation/api/dependencies/documents.py`) сами
    # импортируют accessor-функции этого модуля (`get_settings` и т.п.) —
    # импорт на уровне модуля создал бы цикл `bootstrap.application` ->
    # `presentation.api.routes.admin_documents` -> `presentation.api.
    # dependencies.documents` -> `bootstrap.application`.
    from dekoder.presentation.api.routes.admin_documents import router as admin_documents_router
    from dekoder.presentation.api.routes.admin_profiles import router as admin_profiles_router

    app.include_router(admin_documents_router)
    app.include_router(admin_profiles_router)
    app.add_exception_handler(DekoderError, dekoder_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
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


def get_settings(request: Request) -> Settings:
    """
    FastAPI-зависимость: доступ к `Settings` через `request.app.state`
    (S8-03, ADR-8.2) — тем же приёмом, что и `get_container`. Нужен
    admin-зависимостям (`require_admin_api_key`, `presentation/api/
    dependencies/documents.py`), которым не подходит `ApplicationContainer`
    целиком (например, авторизация не должна тянуть за собой весь
    диалоговый контейнер).
    """
    settings: Settings = request.app.state.settings
    return settings


def get_db_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    """FastAPI-зависимость: единая фабрика сессий БД (S8-03) — нужна per-request сессии admin-документных роутов."""
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.db_session_factory
    return session_factory


def get_openai_http_client(request: Request) -> httpx.AsyncClient:
    """FastAPI-зависимость: уже открытый клиент OpenAI (эмбеддинги, S8-03) — не создаёт новый клиент."""
    client: httpx.AsyncClient = request.app.state.openai_http_client
    return client


def get_qdrant_client(request: Request) -> AsyncQdrantClient:
    """FastAPI-зависимость: уже открытый клиент Qdrant (S8-03) — не создаёт новый клиент."""
    client: AsyncQdrantClient = request.app.state.qdrant_client
    return client
