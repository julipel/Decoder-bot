"""
Интеграционные тесты `SQLAlchemyWebSearchSettingRepository` (внеспринтовая
задача, 2026-09-09) на временной SQLite-базе (`tmp_path` — НЕ рабочая БД).
Стиль fixture'ов — прямой прецедент `tests/integration/persistence/
test_model_selection_repository.py`: схема создаётся через `Base.metadata.
create_all()`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.infrastructure.persistence.sqlalchemy_web_search_setting_repository import (
    SQLAlchemyWebSearchSettingRepository,
)
from dekoder.infrastructure.persistence.user_orm import UserORM
from dekoder.infrastructure.persistence.user_web_search_setting_orm import UserWebSearchSettingORM


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'web-search-setting-repository.db'}"
    test_engine = create_database_engine(database_url)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker:  # type: ignore[type-arg]
    return create_session_factory(engine)


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None)


async def _make_user(session_factory: async_sessionmaker, telegram_user_id: int) -> UUID:  # type: ignore[type-arg]
    now = _now()
    async with session_factory() as session:
        user = UserORM(id=uuid4(), telegram_user_id=telegram_user_id, created_at=now, updated_at=now)
        session.add(user)
        await session.commit()
        return user.id


class TestGetEnabledWithoutRecord:
    """Отсутствие записи для пользователя — штатное «выключено», не исключение."""

    async def test_returns_false_when_no_setting_saved(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        user_id = await _make_user(session_factory, 111)

        async with session_factory() as session:
            repository = SQLAlchemyWebSearchSettingRepository(session)
            enabled = await repository.get_enabled(user_id)

        assert enabled is False


class TestSetEnabledPersistsChoice:
    """Upsert — повторная установка заменяет предыдущее значение, не дублирует строку."""

    async def test_enabled_flag_is_persisted(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        user_id = await _make_user(session_factory, 222)

        async with session_factory() as session:
            repository = SQLAlchemyWebSearchSettingRepository(session)
            await repository.set_enabled(user_id, True)

        async with session_factory() as session:
            repository = SQLAlchemyWebSearchSettingRepository(session)
            enabled = await repository.get_enabled(user_id)

        assert enabled is True

    async def test_repeated_toggle_replaces_previous_value_without_duplicating_row(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        user_id = await _make_user(session_factory, 333)

        async with session_factory() as session:
            repository = SQLAlchemyWebSearchSettingRepository(session)
            await repository.set_enabled(user_id, True)

        async with session_factory() as session:
            repository = SQLAlchemyWebSearchSettingRepository(session)
            await repository.set_enabled(user_id, False)

        async with session_factory() as session:
            repository = SQLAlchemyWebSearchSettingRepository(session)
            enabled = await repository.get_enabled(user_id)

        assert enabled is False

        async with session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(UserWebSearchSettingORM).where(UserWebSearchSettingORM.user_id == user_id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 1
            assert rows[0].enabled is False


class TestUserIsolation:
    """Настройка одного пользователя не видна/не влияет на другого."""

    async def test_two_users_keep_independent_settings(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        user_a = await _make_user(session_factory, 444)
        user_b = await _make_user(session_factory, 555)

        async with session_factory() as session:
            repository = SQLAlchemyWebSearchSettingRepository(session)
            await repository.set_enabled(user_a, True)

        async with session_factory() as session:
            repository = SQLAlchemyWebSearchSettingRepository(session)
            enabled_a = await repository.get_enabled(user_a)
            enabled_b = await repository.get_enabled(user_b)

        assert enabled_a is True
        assert enabled_b is False
