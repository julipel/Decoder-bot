"""
Интеграционные тесты `SQLAlchemyUserRepository` (задача S2-03) на
временной SQLite-базе (`tmp_path` — НЕ рабочая БД). Стиль fixture'ов — как
в `tests/integration/persistence/test_orm_constraints.py`: схема создаётся
через `Base.metadata.create_all()` (единственное допустимое исключение для
тестового окружения, backlog_2.md §3).

Ключевой тест — `TestConcurrentGetOrCreate`: два конкурентных вызова
`get_or_create_by_telegram_user_id()` с одним и тем же `telegram_user_id`
(`asyncio.gather`, каждый — на собственной независимой `AsyncSession`)
должны вернуть пользователя с одним и тем же внутренним `id`, а в базе
должна остаться ровно одна строка — гонка разрешается уникальным
ограничением `uq_users_telegram_user_id` на уровне БД (S2-02), не
проверкой на уровне Python.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from dekoder.domain.user.entities import User
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.infrastructure.persistence.user_orm import UserORM
from dekoder.infrastructure.persistence.user_repository import SQLAlchemyUserRepository
from dekoder.shared.errors import InfrastructureError


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'user-repository.db'}"
    test_engine = create_database_engine(database_url)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker:  # type: ignore[type-arg]
    return create_session_factory(engine)


def _make_user(telegram_user_id: int) -> User:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    return User(id=uuid4(), telegram_user_id=telegram_user_id, created_at=now, updated_at=now)


class TestGetById:
    async def test_returns_none_when_not_found(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            repository = SQLAlchemyUserRepository(session)
            result = await repository.get_by_id(uuid4())

        assert result is None

    async def test_returns_existing_user(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            repository = SQLAlchemyUserRepository(session)
            created = await repository.get_or_create_by_telegram_user_id(1001)

        async with session_factory() as session:
            repository = SQLAlchemyUserRepository(session)
            result = await repository.get_by_id(created.id)

        assert result == created
        assert isinstance(result, User)
        assert not isinstance(result, UserORM)


class TestGetByTelegramUserId:
    async def test_returns_none_when_not_found(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            repository = SQLAlchemyUserRepository(session)
            result = await repository.get_by_telegram_user_id(999999)

        assert result is None

    async def test_returns_existing_user(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            repository = SQLAlchemyUserRepository(session)
            created = await repository.get_or_create_by_telegram_user_id(1002)

        async with session_factory() as session:
            repository = SQLAlchemyUserRepository(session)
            result = await repository.get_by_telegram_user_id(1002)

        assert result == created


class TestSave:
    async def test_save_persists_new_user(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        user = _make_user(1003)
        async with session_factory() as session:
            repository = SQLAlchemyUserRepository(session)
            saved = await repository.save(user)
            await session.commit()

        assert saved == user

        async with session_factory() as session:
            stored = (await session.execute(select(UserORM).where(UserORM.telegram_user_id == 1003))).scalar_one()
            assert stored.id == user.id

    async def test_save_duplicate_telegram_user_id_raises_infrastructure_error(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            repository = SQLAlchemyUserRepository(session)
            await repository.save(_make_user(1004))
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyUserRepository(session)
            with pytest.raises(InfrastructureError):
                await repository.save(_make_user(1004))


class TestGetOrCreateByTelegramUserId:
    async def test_creates_user_when_not_found(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            repository = SQLAlchemyUserRepository(session)
            created = await repository.get_or_create_by_telegram_user_id(1005)

        assert created.telegram_user_id == 1005

    async def test_repeated_calls_return_the_same_internal_id(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            repository = SQLAlchemyUserRepository(session)
            first = await repository.get_or_create_by_telegram_user_id(1006)

        async with session_factory() as session:
            repository = SQLAlchemyUserRepository(session)
            second = await repository.get_or_create_by_telegram_user_id(1006)

        assert first.id == second.id
        assert first == second

        async with session_factory() as session:
            rows = (await session.execute(select(UserORM).where(UserORM.telegram_user_id == 1006))).scalars().all()
        assert len(rows) == 1


class TestConcurrentGetOrCreate:
    """
    Обязательный тест конкурентности (backlog_2.md §8, «Конкурентный
    доступ»): две почти одновременные попытки создать пользователя с
    одним и тем же `telegram_user_id`, каждая на собственной независимой
    `AsyncSession`, должны в итоге сойтись на одном и том же внутреннем
    `id`, без дублей в БД. Гонка разрешается тем, что вторая транзакция
    падает `IntegrityError` на уникальном ограничении БД, откатывается и
    повторно находит запись, созданную первой транзакцией.
    """

    async def test_concurrent_calls_converge_on_the_same_user_without_duplicates(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        telegram_user_id = 2001

        async def _get_or_create() -> User:
            async with session_factory() as session:
                repository = SQLAlchemyUserRepository(session)
                return await repository.get_or_create_by_telegram_user_id(telegram_user_id)

        first, second = await asyncio.gather(_get_or_create(), _get_or_create())

        assert first.id == second.id
        assert first == second

        async with session_factory() as session:
            rows = (
                (await session.execute(select(UserORM).where(UserORM.telegram_user_id == telegram_user_id)))
                .scalars()
                .all()
            )
        assert len(rows) == 1
