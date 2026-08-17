"""
Интеграционные тесты `SQLAlchemyModelSelectionRepository` (Sprint 7, задача
S7-04, ADR-7.5) на временной SQLite-базе (`tmp_path` — НЕ рабочая БД).
Стиль fixture'ов — прямой прецедент `tests/integration/persistence/
test_profile_repository.py`: схема создаётся через `Base.metadata.
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

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.infrastructure.persistence.sqlalchemy_model_selection_repository import (
    SQLAlchemyModelSelectionRepository,
)
from dekoder.infrastructure.persistence.user_active_model_orm import UserActiveModelORM
from dekoder.infrastructure.persistence.user_orm import UserORM


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'model-selection-repository.db'}"
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


class TestGetSelectedWithoutChoice:
    """AC (ADR-7.5 DoD): `get_selected` для пользователя без выбора возвращает `None`."""

    async def test_returns_none_when_no_selection_made(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        user_id = await _make_user(session_factory, 111)

        async with session_factory() as session:
            repository = SQLAlchemyModelSelectionRepository(session)
            selected = await repository.get_selected(user_id)

        assert selected is None


class TestSelectPersistsChoice:
    """AC-1 (backlog_7_tasks.md S7-04): upsert — повторный выбор заменяет предыдущий, не дублирует строку."""

    async def test_selected_model_becomes_active(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        user_id = await _make_user(session_factory, 222)

        async with session_factory() as session:
            repository = SQLAlchemyModelSelectionRepository(session)
            await repository.select(user_id, ModelId("anthropic/claude-3.5-sonnet"))

        async with session_factory() as session:
            repository = SQLAlchemyModelSelectionRepository(session)
            selected = await repository.get_selected(user_id)

        assert selected == ModelId("anthropic/claude-3.5-sonnet")

    async def test_repeated_selection_replaces_previous_choice_without_duplicating_row(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        user_id = await _make_user(session_factory, 333)

        async with session_factory() as session:
            repository = SQLAlchemyModelSelectionRepository(session)
            await repository.select(user_id, ModelId("openai/gpt-4o-mini"))

        async with session_factory() as session:
            repository = SQLAlchemyModelSelectionRepository(session)
            await repository.select(user_id, ModelId("anthropic/claude-3.5-sonnet"))

        async with session_factory() as session:
            repository = SQLAlchemyModelSelectionRepository(session)
            selected = await repository.get_selected(user_id)

        assert selected == ModelId("anthropic/claude-3.5-sonnet")

        async with session_factory() as session:
            rows = (
                (await session.execute(select(UserActiveModelORM).where(UserActiveModelORM.user_id == user_id)))
                .scalars()
                .all()
            )
            assert len(rows) == 1
            assert rows[0].model_id == "anthropic/claude-3.5-sonnet"


class TestUserIsolation:
    """AC-2 (backlog_7_tasks.md S7-04): выбор одного пользователя не виден/не влияет на другого."""

    async def test_two_users_keep_independent_selections(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        user_a = await _make_user(session_factory, 444)
        user_b = await _make_user(session_factory, 555)

        async with session_factory() as session:
            repository = SQLAlchemyModelSelectionRepository(session)
            await repository.select(user_a, ModelId("openai/gpt-4o-mini"))

        async with session_factory() as session:
            repository = SQLAlchemyModelSelectionRepository(session)
            await repository.select(user_b, ModelId("anthropic/claude-3.5-sonnet"))

        async with session_factory() as session:
            repository = SQLAlchemyModelSelectionRepository(session)
            selected_a = await repository.get_selected(user_a)
            selected_b = await repository.get_selected(user_b)

        assert selected_a == ModelId("openai/gpt-4o-mini")
        assert selected_b == ModelId("anthropic/claude-3.5-sonnet")
