"""
Фабрика единого `AsyncEngine` (SQLAlchemy 2.x async API, Infrastructure
Layer) и проверка доступности базы данных при старте приложения.

Единственный драйвер SQLite — `aiosqlite`; синхронный и асинхронный
SQLAlchemy API не смешиваются (задача S2-01, backlog_2.md §5).

`create_database_engine()` — единственное место, которое включает
`PRAGMA foreign_keys=ON` для каждого нового низкоуровневого соединения
SQLite: централизованно на уровне engine, а не вручную в каждом будущем
репозитории.

Domain и Application Layer не импортируют этот модуль — единый
`AsyncEngine` создаётся исключительно в bootstrap-слое
(`bootstrap/database.py`) и передаётся туда, где он нужен, а не
создаётся заново внутри use case (claude.md §6/§24, backlog_2.md §5).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from dekoder.shared.errors import InfrastructureError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


def create_database_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """
    Создаёт единый `AsyncEngine` для приложения на основе `DATABASE_URL`.

    `echo` не включён по умолчанию (`False`) — SQL-запросы не логируются
    в проде по умолчанию (требование задачи S2-01); значение передаёт
    вызывающий bootstrap-код осознанно (например, только для локальной
    отладки).

    Ошибка некорректного URL превращается в `InfrastructureError` —
    приложение не должно тихо продолжать запуск с нерабочей конфигурацией
    базы данных.
    """
    try:
        masked_url = make_url(database_url).render_as_string(hide_password=True)
    except ArgumentError as exc:
        _logger.error("database_engine_invalid_url", error=str(exc))
        raise InfrastructureError(
            message=f"Invalid DATABASE_URL: {exc}",
            user_message="Не удалось подключиться к базе данных приложения.",
            code="DATABASE_INVALID_URL",
            cause=exc,
        ) from exc

    engine = create_async_engine(database_url, echo=echo)

    if engine.dialect.name == "sqlite":
        _register_sqlite_foreign_keys_pragma(engine)

    # Логируется URL БЕЗ пароля (`hide_password=True`) — требование задачи
    # S2-01: не логировать DATABASE_URL целиком, если в нём есть секрет.
    _logger.info("database_engine_initialized", database_url=masked_url, dialect=engine.dialect.name)
    return engine


def _register_sqlite_foreign_keys_pragma(engine: AsyncEngine) -> None:
    """
    Включает `PRAGMA foreign_keys=ON` для каждого нового DBAPI-соединения
    SQLite. Слушатель регистрируется на `engine.sync_engine`, потому что
    событие DBAPI `"connect"` синхронное даже для `aiosqlite` (обёртка
    выполняет реальное `sqlite3.connect()` в фоновом потоке и сама
    вызывает этот синхронный колбэк) — асинхронный listener здесь не нужен
    и не поддерживается SQLAlchemy для этого события.
    """

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


async def verify_database_connection(engine: AsyncEngine) -> None:
    """
    Проверяет, что база данных реально доступна: открывает соединение и
    выполняет `SELECT 1`. Вызывается один раз при старте процесса
    (`bootstrap/database.py`) — ошибка подключения должна останавливать
    запуск приложения с понятным сообщением (fail-fast), а не проявляться
    позже как ошибка первого пользовательского запроса, и не приводить к
    молчаливому переключению на in-memory SQLite.
    """
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        _logger.error("database_connection_failed", error=str(exc))
        raise InfrastructureError(
            message=f"Database connection failed: {exc}",
            user_message="Сервис временно недоступен: не удалось подключиться к базе данных.",
            code="DATABASE_CONNECTION_FAILED",
            cause=exc,
        ) from exc
    _logger.info("database_connection_verified")
