"""
Тесты `infrastructure/persistence/engine.py` (S2-01): создание единого
`AsyncEngine`, включение `PRAGMA foreign_keys=ON` для каждого нового
SQLite-соединения, проверка доступности базы данных при старте.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from dekoder.infrastructure.persistence.engine import create_database_engine, verify_database_connection
from dekoder.shared.errors import InfrastructureError


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite+aiosqlite:///{db_path}"


class TestCreateDatabaseEngine:
    async def test_returns_async_sqlite_engine(self, tmp_path: Path) -> None:
        engine = create_database_engine(_sqlite_url(tmp_path / "engine.db"))

        assert isinstance(engine, AsyncEngine)
        assert engine.dialect.name == "sqlite"

        await engine.dispose()

    async def test_echo_is_false_by_default(self, tmp_path: Path) -> None:
        engine = create_database_engine(_sqlite_url(tmp_path / "echo.db"))

        assert engine.echo is False

        await engine.dispose()

    async def test_echo_can_be_explicitly_enabled(self, tmp_path: Path) -> None:
        engine = create_database_engine(_sqlite_url(tmp_path / "echo-on.db"), echo=True)

        assert engine.echo is True

        await engine.dispose()

    def test_invalid_url_raises_infrastructure_error_not_silently(self) -> None:
        with pytest.raises(InfrastructureError) as exc_info:
            create_database_engine("not-a-valid-database-url")

        assert exc_info.value.code == "DATABASE_INVALID_URL"


class TestForeignKeysPragma:
    async def test_foreign_keys_are_enabled_for_every_new_connection(self, tmp_path: Path) -> None:
        engine = create_database_engine(_sqlite_url(tmp_path / "fk.db"))

        async with engine.connect() as first_connection:
            result = await first_connection.execute(text("PRAGMA foreign_keys"))
            assert result.scalar_one() == 1

        # Открывается ещё одно, отдельное соединение — pragma должна
        # включаться централизованно для КАЖДОГО нового DBAPI-соединения,
        # а не один раз при создании engine.
        async with engine.connect() as second_connection:
            result = await second_connection.execute(text("PRAGMA foreign_keys"))
            assert result.scalar_one() == 1

        await engine.dispose()


class TestVerifyDatabaseConnection:
    async def test_succeeds_for_a_reachable_sqlite_database(self, tmp_path: Path) -> None:
        engine = create_database_engine(_sqlite_url(tmp_path / "reachable.db"))

        await verify_database_connection(engine)

        await engine.dispose()

    async def test_raises_infrastructure_error_for_unreachable_database(self, tmp_path: Path) -> None:
        # Родительский каталог сознательно не создан — sqlite не сможет
        # открыть файл, соединение завершится ошибкой.
        unreachable_path = tmp_path / "missing-directory" / "unreachable.db"
        engine = create_database_engine(_sqlite_url(unreachable_path))

        with pytest.raises(InfrastructureError) as exc_info:
            await verify_database_connection(engine)

        assert exc_info.value.code == "DATABASE_CONNECTION_FAILED"

        await engine.dispose()
