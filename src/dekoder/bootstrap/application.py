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
from dekoder.shared.config import Settings
from dekoder.shared.logging import configure_logging


def create_application(settings: Settings) -> FastAPI:
    configure_logging(
        environment=settings.application.environment,
        level="DEBUG" if settings.application.debug else "INFO",
    )

    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        db_engine, db_session_factory = await init_database(settings)
        try:
            async with httpx.AsyncClient(
                base_url=settings.openrouter.base_url,
                timeout=settings.llm.timeout,
            ) as http_client:
                app.state.container = build_container(settings, http_client)
                app.state.db_engine = db_engine
                app.state.db_session_factory = db_session_factory
                yield
                # Дошли сюда при остановке приложения: `async with` сейчас
                # выйдет из блока и закроет http_client (httpx.AsyncClient.
                # __aexit__) — единственное место, где клиент закрывается.
        finally:
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
