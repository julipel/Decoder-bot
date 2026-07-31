"""
Интеграционные тесты `SQLAlchemyConversationRepository` (задача S2-04) на
временной SQLite-базе (`tmp_path` — НЕ рабочая БД). Стиль fixture'ов — как
в `tests/integration/persistence/test_user_repository.py`.

Ключевые тесты:
- `TestOneActiveConversationInvariant` — второй активный диалог того же
  пользователя должен быть отклонён БД (частичный уникальный индекс
  `uq_conversations_active_user`, S2-02), закрытие первого открывает
  дорогу новому активному.
- `TestConcurrentGetOrCreateActive` — обязательный тест конкурентности
  (backlog_2.md §8): два конкурентных вызова `get_or_create_active()` с
  одним и тем же `user_id`, каждый на собственной независимой
  `AsyncSession`, должны сойтись на одном и том же `id`, в БД — ровно
  одна активная строка.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from dekoder.domain.conversation.entities import Conversation
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.conversation_orm import ConversationORM
from dekoder.infrastructure.persistence.conversation_repository import SQLAlchemyConversationRepository
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.infrastructure.persistence.user_orm import UserORM
from dekoder.shared.errors import InfrastructureError


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'conversation-repository.db'}"
    test_engine = create_database_engine(database_url)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker:  # type: ignore[type-arg]
    return create_session_factory(engine)


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


async def _persist_user(session: AsyncSession, telegram_user_id: int) -> UUID:
    """Создаёт пользователя напрямую через ORM (репозиторий пользователей — вне области S2-04)."""
    now = _now()
    user = UserORM(id=uuid4(), telegram_user_id=telegram_user_id, created_at=now, updated_at=now)
    session.add(user)
    await session.commit()
    return user.id


def _make_conversation(user_id: UUID, *, closed_at: datetime | None = None) -> Conversation:
    now = _now()
    return Conversation(id=uuid4(), user_id=user_id, created_at=now, updated_at=closed_at or now, closed_at=closed_at)


class TestGetById:
    async def test_returns_none_when_not_found(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            repository = SQLAlchemyConversationRepository(session)
            result = await repository.get_by_id(uuid4())

        assert result is None

    async def test_save_and_get_by_id_round_trips_all_fields(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 5001)
            repository = SQLAlchemyConversationRepository(session)
            conversation = _make_conversation(user_id)
            saved = await repository.save(conversation)
            await session.commit()

        assert saved == conversation

        async with session_factory() as session:
            repository = SQLAlchemyConversationRepository(session)
            fetched = await repository.get_by_id(conversation.id)

        assert fetched == conversation
        assert isinstance(fetched, Conversation)
        assert not isinstance(fetched, ConversationORM)


class TestGetActiveByUserId:
    async def test_returns_none_when_no_conversation_exists(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 5002)
            repository = SQLAlchemyConversationRepository(session)
            result = await repository.get_active_by_user_id(user_id)

        assert result is None

    async def test_finds_active_and_ignores_closed(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 5003)
            repository = SQLAlchemyConversationRepository(session)
            closed = _make_conversation(user_id, closed_at=_now())
            await repository.save(closed)
            await session.commit()

            active = await repository.get_or_create_active(user_id)

        async with session_factory() as session:
            repository = SQLAlchemyConversationRepository(session)
            result = await repository.get_active_by_user_id(user_id)

        assert result == active
        # Возвращённая сущность — чистый domain-объект без коллекции
        # messages (никакого eager-load истории, backlog_2.md §8).
        assert not hasattr(result, "messages")

    async def test_returns_none_when_only_closed_conversation_exists(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 5004)
            repository = SQLAlchemyConversationRepository(session)
            closed = _make_conversation(user_id, closed_at=_now())
            await repository.save(closed)
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyConversationRepository(session)
            result = await repository.get_active_by_user_id(user_id)

        assert result is None


class TestForeignKeyEnforcement:
    async def test_save_with_unknown_user_id_raises_infrastructure_error_and_persists_nothing(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        unknown_user_id = uuid4()
        async with session_factory() as session:
            repository = SQLAlchemyConversationRepository(session)
            with pytest.raises(InfrastructureError):
                await repository.save(_make_conversation(unknown_user_id))

        async with session_factory() as session:
            rows = (
                (await session.execute(select(ConversationORM).where(ConversationORM.user_id == unknown_user_id)))
                .scalars()
                .all()
            )
        assert rows == []


class TestClose:
    async def test_close_updates_only_closed_at_and_updated_at(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 5005)
            repository = SQLAlchemyConversationRepository(session)
            conversation = await repository.get_or_create_active(user_id)

        closed_at = conversation.created_at + timedelta(hours=1)
        conversation.close(closed_at)

        async with session_factory() as session:
            repository = SQLAlchemyConversationRepository(session)
            closed = await repository.close(conversation)
            await session.commit()

        assert closed.closed_at == closed_at
        assert closed.updated_at == closed_at

        async with session_factory() as session:
            repository = SQLAlchemyConversationRepository(session)
            fetched = await repository.get_by_id(conversation.id)

        assert fetched is not None
        assert fetched.id == conversation.id
        assert fetched.user_id == user_id
        assert fetched.created_at == conversation.created_at
        assert fetched.closed_at == closed_at
        assert fetched.updated_at == closed_at

        # Диалог не удалён, остаётся читаемым, больше не активен.
        async with session_factory() as session:
            repository = SQLAlchemyConversationRepository(session)
            active = await repository.get_active_by_user_id(user_id)

        assert active is None


class TestOneActiveConversationInvariant:
    """
    Обязательный тест задачи S2-04: у пользователя не может быть двух
    активных диалогов — БД должна отклонить попытку сохранить второй.
    """

    async def test_second_active_conversation_is_rejected_then_succeeds_after_closing_the_first(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 5006)

        # Первый активный диалог создаётся успешно.
        async with session_factory() as session:
            repository = SQLAlchemyConversationRepository(session)
            first_active = await repository.save(_make_conversation(user_id))
            await session.commit()

        # Попытка сохранить второй активный диалог того же пользователя
        # должна упасть с InfrastructureError (обёрнутый IntegrityError),
        # а не пройти молча.
        async with session_factory() as session:
            repository = SQLAlchemyConversationRepository(session)
            with pytest.raises(InfrastructureError):
                await repository.save(_make_conversation(user_id))

        # Закрываем первый активный диалог...
        closed_at = _now() + timedelta(hours=2)
        first_active.close(closed_at)
        async with session_factory() as session:
            repository = SQLAlchemyConversationRepository(session)
            await repository.close(first_active)
            await session.commit()

        # ...теперь сохранение нового активного диалога проходит успешно.
        async with session_factory() as session:
            repository = SQLAlchemyConversationRepository(session)
            third_active = await repository.save(_make_conversation(user_id))
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyConversationRepository(session)
            active = await repository.get_active_by_user_id(user_id)

        assert active == third_active


class TestGetOrCreateActive:
    async def test_creates_active_conversation_when_none_exists(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 5007)
            repository = SQLAlchemyConversationRepository(session)
            created = await repository.get_or_create_active(user_id)

        assert created.user_id == user_id
        assert created.closed_at is None

    async def test_repeated_calls_return_the_same_conversation(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 5008)

        async with session_factory() as session:
            repository = SQLAlchemyConversationRepository(session)
            first = await repository.get_or_create_active(user_id)

        async with session_factory() as session:
            repository = SQLAlchemyConversationRepository(session)
            second = await repository.get_or_create_active(user_id)

        assert first.id == second.id
        assert first == second

        async with session_factory() as session:
            rows = (
                (await session.execute(select(ConversationORM).where(ConversationORM.user_id == user_id)))
                .scalars()
                .all()
            )
        assert len(rows) == 1


class TestConcurrentGetOrCreateActive:
    """
    Обязательный тест конкурентности (backlog_2.md §8, «Конкурентный
    доступ»): две почти одновременные попытки создать активный диалог
    одного и того же пользователя, каждая на собственной независимой
    `AsyncSession`, должны в итоге сойтись на одном и том же `id`, без
    дублей в БД. Гонка разрешается тем, что вторая транзакция падает
    `IntegrityError` на уникальном ограничении БД, откатывается и
    повторно находит запись, созданную первой транзакцией.
    """

    async def test_concurrent_calls_converge_on_the_same_conversation_without_duplicates(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 5009)

        async def _get_or_create() -> Conversation:
            async with session_factory() as session:
                repository = SQLAlchemyConversationRepository(session)
                return await repository.get_or_create_active(user_id)

        first, second = await asyncio.gather(_get_or_create(), _get_or_create())

        assert first.id == second.id
        assert first == second

        async with session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ConversationORM).where(
                            ConversationORM.user_id == user_id, ConversationORM.closed_at.is_(None)
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert len(rows) == 1
