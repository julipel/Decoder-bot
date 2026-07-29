"""
Сборка приложения: конфигурация → контейнер → HTTP/Telegram driving adapters.

При старте приложения незавершённые задания индексации переводятся в
состояние, допускающее повторный запуск (см. docs/versions/02_system_architecture_v2.0.md,
§12 — обработка ошибок индексации).
"""

from __future__ import annotations

from fastapi import FastAPI

from dekoder.composition.container import Container
from dekoder.composition.health import APP_NAME, APP_VERSION
from dekoder.composition.health import router as health_router
from dekoder.shared.config import Settings
from dekoder.shared.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Собирает ASGI-приложение: FastAPI-инстанс + системный `/health`.

    `settings` принимается параметром, а не читается глобально внутри
    функции — создание `Settings()` происходит в bootstrap-слое
    (`main.py`), а не здесь и не при импорте `shared.config`/`shared.
    logging` — это позволяет подставлять тестовые настройки без
    переменных окружения. Без `settings` (например, в тестах) логирование
    настраивается с `environment="unknown"`, а не падает и не требует
    секретов. DI-контейнер (`build_container`), HTTP-роуты панели
    администратора, Telegram driving adapter и восстановление
    незавершённой индексации (`recover_interrupted_indexing_jobs`)
    подключаются здесь на следующем шаге — вне объёма текущей задачи.
    """
    configure_logging(
        environment=settings.application.environment if settings else "unknown",
        level="DEBUG" if settings and settings.application.debug else "INFO",
    )
    app = FastAPI(title=APP_NAME, version=APP_VERSION)
    app.include_router(health_router)
    return app


def recover_interrupted_indexing_jobs(container: Container) -> None:
    """Переводит документы со статусом «ожидает индексации» дольше ожидаемого в повторно запускаемое состояние."""
    raise NotImplementedError
