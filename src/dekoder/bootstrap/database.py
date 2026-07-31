"""
Инициализация постоянного хранилища данных — bootstrap-слой (единственное
место, которому разрешено знать одновременно про `Settings.database.url` и
конкретный SQLAlchemy `AsyncEngine`, задача S2-01).

`init_database()` — единственная точка инициализации хранилища для реально
запускаемого приложения (`bootstrap/application.py` для API-процесса,
`telegram_main.py` для процесса polling). Она:

- разрешает путь SQLite-файла из `DATABASE_URL` и создаёт его родительский
  каталог (например, `./data/`), если он ещё не существует, — только
  каталог, не файл базы данных и не таблицы (файл создаёт драйвер при
  первом подключении, таблицы создаёт исключительно Alembic, см.
  `alembic/env.py`, backlog_2.md §5/§15, инвариант 12);
- создаёт единый `AsyncEngine` и единую фабрику сессий
  (`infrastructure/persistence/{engine,session}.py`);
- проверяет, что база данных реально доступна (`SELECT 1`), до того как
  приложение начнёт принимать трафик — ошибка подключения останавливает
  запуск процесса (fail-fast) вместо того, чтобы молча продолжить или
  переключиться на in-memory SQLite.

Эта задача (S2-01) не вводит ORM-модели и репозитории — возвращённые
`AsyncEngine`/`async_sessionmaker` пока не используются ни одним use
case; они подготавливают инфраструктуру для следующей задачи Sprint 2.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from dekoder.infrastructure.persistence.engine import create_database_engine, verify_database_connection
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.shared.config import Settings
from dekoder.shared.errors import InfrastructureError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


def _ensure_sqlite_directory_exists(database_url: str) -> None:
    """
    Для `sqlite+aiosqlite:///./data/app.db` создаёт каталог `./data/`, если
    его ещё нет. Не создаёт сам файл базы данных (это делает драйвер при
    первом подключении) и не создаёт таблицы (это делает только Alembic).
    Не-SQLite диалекты и in-memory базы (`:memory:`) пропускаются — для них
    родительского каталога на диске не существует.
    """
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return
    database_path = url.database
    if not database_path or database_path == ":memory:":
        return
    try:
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _logger.error("database_directory_creation_failed", error=str(exc))
        raise InfrastructureError(
            message=f"Could not create directory for the SQLite database file: {exc}",
            user_message="Не удалось подготовить хранилище данных приложения.",
            code="DATABASE_DIRECTORY_UNAVAILABLE",
            cause=exc,
        ) from exc


async def init_database(settings: Settings) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """
    Готовит постоянное хранилище к использованию: каталог → engine →
    проверка подключения → фабрика сессий. Вызывающий код отвечает за
    жизненный цикл возвращённого `AsyncEngine` (`await engine.dispose()`
    при остановке процесса, в том же event loop, в котором он был создан —
    `aiosqlite`-соединения привязаны к конкретному loop'у).
    """
    database_url = settings.database.url

    # echo привязан к APP_DEBUG, а не включён по умолчанию — SQL-запросы не
    # логируются в проде (требование задачи S2-01); значение по умолчанию
    # APP_DEBUG=false, поэтому echo остаётся False, пока не включён явно.
    # Создаётся раньше проверки каталога: `create_database_engine` уже
    # валидирует сам URL и превращает некорректное значение в понятную
    # `InfrastructureError`, не давая двум местам параллельно парсить URL.
    engine = create_database_engine(database_url, echo=settings.application.debug)
    _ensure_sqlite_directory_exists(database_url)
    await verify_database_connection(engine)

    session_factory = create_session_factory(engine)
    return engine, session_factory


async def dispose_database(engine: AsyncEngine) -> None:
    """Закрывает пул соединений `AsyncEngine` при остановке процесса."""
    await engine.dispose()
    _logger.info("database_engine_disposed")
