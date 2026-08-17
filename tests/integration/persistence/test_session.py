"""
Тесты `infrastructure/persistence/session.py` (S2-01) — единого механизма
управления сессиями: `create_session_factory` и `session_scope`.

Задача S2-01 не вводит ORM-модели, поэтому здесь используется одна
временная таблица, созданная напрямую SQL (`CREATE TABLE`), — только для
проверки поведения сессии (commit/rollback/закрытие), а не как часть
рабочей схемы приложения (та создаётся исключительно через Alembic).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from dekoder.infrastructure.persistence.session import create_session_factory, session_scope


class _Boom(Exception):
    """Маркерное исключение для теста rollback — не часть иерархии DekoderError намеренно."""


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'session-scope.db'}"
    test_engine = create_async_engine(database_url)
    async with test_engine.begin() as connection:
        await connection.execute(text("CREATE TABLE greeting (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT)"))
    yield test_engine
    await test_engine.dispose()


class TestCreateSessionFactory:
    async def test_produces_sessions_with_required_settings(self, engine: AsyncEngine) -> None:
        session_factory = create_session_factory(engine)

        async with session_factory() as session:
            assert session.sync_session.autoflush is False
        # expire_on_commit=False проверяется поведенчески в TestSessionScope.commits_on_success.


class TestSessionScope:
    async def test_commits_on_successful_completion(self, engine: AsyncEngine) -> None:
        session_factory = create_session_factory(engine)

        async with session_scope(session_factory) as session:
            await session.execute(text("INSERT INTO greeting (text) VALUES ('hello')"))

        async with session_factory() as verification_session:
            result = await verification_session.execute(text("SELECT text FROM greeting"))
            assert result.scalars().all() == ["hello"]

    async def test_rolls_back_on_exception_and_propagates_it(self, engine: AsyncEngine) -> None:
        session_factory = create_session_factory(engine)

        with pytest.raises(_Boom):
            async with session_scope(session_factory) as session:
                await session.execute(text("INSERT INTO greeting (text) VALUES ('should-not-persist')"))
                raise _Boom("simulated failure")

        async with session_factory() as verification_session:
            result = await verification_session.execute(text("SELECT COUNT(*) FROM greeting"))
            assert result.scalar_one() == 0

    async def test_releases_connection_back_to_the_pool_after_use(self, engine: AsyncEngine) -> None:
        session_factory = create_session_factory(engine)

        async with session_scope(session_factory) as session:
            await session.execute(text("SELECT 1"))

        assert engine.pool.checkedout() == 0

    async def test_each_call_creates_an_independent_session(self, engine: AsyncEngine) -> None:
        session_factory = create_session_factory(engine)

        async with session_scope(session_factory) as first_session:
            pass
        async with session_scope(session_factory) as second_session:
            pass

        assert first_session is not second_session
