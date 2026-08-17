"""
Интеграционные тесты `SQLAlchemyMemoryRepository` (Sprint 5, задача S5-04,
ADR-5.6/ADR-5.7/ADR-5.10) на временной SQLite-базе (`tmp_path` — НЕ
рабочая БД). Стиль fixture'ов — как в `tests/integration/persistence/
test_profile_repository.py`/`test_message_repository.py`.

Ключевые тесты (Definition of Done S5-04, AC-1/AC-2/AC-3):
- `TestFindRelevant` — только `CONFIRMED` и не истёкшие записи, лимит,
  порядок `confidence DESC, created_at DESC`.
- `TestDeleteIsolatesUsers` — `delete()` не удаляет запись другого
  пользователя.
- `TestListConfirmedByUser` — только `CONFIRMED`, без ограничения `limit`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import (
    MemoryCategory,
    MemoryConfidence,
    MemorySource,
    MemoryStatus,
)
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.memory_repository import SQLAlchemyMemoryRepository
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.infrastructure.persistence.user_orm import UserORM
from dekoder.shared.errors import InfrastructureError


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'memory-repository.db'}"
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
    now = _now().replace(tzinfo=None)
    user = UserORM(id=uuid4(), telegram_user_id=telegram_user_id, created_at=now, updated_at=now)
    session.add(user)
    await session.commit()
    return user.id


def _make_record(
    user_id: UUID,
    *,
    text: str = "Работает Python-разработчиком.",
    category: MemoryCategory = MemoryCategory.FACT,
    source: MemorySource = MemorySource.USER_EXPLICIT,
    status: MemoryStatus = MemoryStatus.CONFIRMED,
    confidence: MemoryConfidence = MemoryConfidence.MEDIUM,
    is_sensitive: bool = False,
    expires_at: datetime | None = None,
    created_at: datetime | None = None,
    record_id: UUID | None = None,
) -> MemoryRecord:
    created = created_at or _now()
    return MemoryRecord(
        id=record_id or uuid4(),
        user_id=user_id,
        text=text,
        category=category,
        source=source,
        status=status,
        confidence=confidence,
        is_sensitive=is_sensitive,
        expires_at=expires_at,
        updated_by="user",
        created_at=created,
        updated_at=created,
    )


class TestSaveAndGetById:
    async def test_save_round_trips_all_fields_via_get_by_id(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 7001)
            repository = SQLAlchemyMemoryRepository(session)
            record = _make_record(
                user_id,
                text="Живёт в Берлине.",
                category=MemoryCategory.PERSONAL,
                is_sensitive=True,
                confidence=MemoryConfidence.HIGH,
            )
            await repository.save(record)
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMemoryRepository(session)
            fetched = await repository.get_by_id(record.id)

        assert fetched == record
        assert fetched is not None
        assert fetched.text == "Живёт в Берлине."
        assert fetched.category is MemoryCategory.PERSONAL
        assert fetched.is_sensitive is True
        assert fetched.confidence is MemoryConfidence.HIGH

    async def test_get_by_id_returns_none_for_unknown_id(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            repository = SQLAlchemyMemoryRepository(session)
            result = await repository.get_by_id(uuid4())

        assert result is None


class TestFindRelevant:
    """AC-1: только CONFIRMED, не истёкшие, лимит, порядок confidence DESC, created_at DESC."""

    async def test_excludes_pending_and_rejected(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 7002)
            repository = SQLAlchemyMemoryRepository(session)
            confirmed = await repository.save(_make_record(user_id, status=MemoryStatus.CONFIRMED, text="confirmed"))
            await repository.save(_make_record(user_id, status=MemoryStatus.PENDING, text="pending"))
            await repository.save(_make_record(user_id, status=MemoryStatus.REJECTED, text="rejected"))
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMemoryRepository(session)
            relevant = await repository.find_relevant(user_id, limit=10)

        assert [record.id for record in relevant] == [confirmed.id]

    async def test_excludes_expired_records(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        # `expires_at` сравнивается с РЕАЛЬНЫМ `datetime.now(UTC)` внутри
        # репозитория (не с фиксированным `_now()` теста) — вычисляем
        # границы от актуального времени, иначе фиксированная дата в
        # прошлом (`_now()` = 2026-01-01) сделала бы "активную" запись
        # уже истёкшей относительно реальных часов.
        real_now = datetime.now(UTC)
        async with session_factory() as session:
            user_id = await _persist_user(session, 7003)
            repository = SQLAlchemyMemoryRepository(session)
            active = await repository.save(
                _make_record(user_id, text="active", expires_at=real_now + timedelta(days=1))
            )
            await repository.save(_make_record(user_id, text="expired", expires_at=real_now - timedelta(days=1)))
            await repository.save(_make_record(user_id, text="no-expiry", expires_at=None))
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMemoryRepository(session)
            relevant = await repository.find_relevant(user_id, limit=10)

        assert active.id in {record.id for record in relevant}
        assert "expired" not in {record.text for record in relevant}
        assert len(relevant) == 2

    async def test_respects_limit(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            user_id = await _persist_user(session, 7004)
            repository = SQLAlchemyMemoryRepository(session)
            for index in range(5):
                await repository.save(_make_record(user_id, text=f"fact {index}"))
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMemoryRepository(session)
            relevant = await repository.find_relevant(user_id, limit=2)

        assert len(relevant) == 2

    async def test_orders_by_confidence_desc_then_created_at_desc(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 7005)
            repository = SQLAlchemyMemoryRepository(session)
            base_time = _now()
            low = await repository.save(
                _make_record(user_id, text="low", confidence=MemoryConfidence.LOW, created_at=base_time)
            )
            high_older = await repository.save(
                _make_record(
                    user_id,
                    text="high-older",
                    confidence=MemoryConfidence.HIGH,
                    created_at=base_time - timedelta(minutes=10),
                )
            )
            high_newer = await repository.save(
                _make_record(
                    user_id,
                    text="high-newer",
                    confidence=MemoryConfidence.HIGH,
                    created_at=base_time + timedelta(minutes=10),
                )
            )
            medium = await repository.save(
                _make_record(user_id, text="medium", confidence=MemoryConfidence.MEDIUM, created_at=base_time)
            )
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMemoryRepository(session)
            relevant = await repository.find_relevant(user_id, limit=10)

        assert [record.id for record in relevant] == [high_newer.id, high_older.id, medium.id, low.id]

    async def test_isolated_between_users(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            user_a = await _persist_user(session, 7006)
            user_b = await _persist_user(session, 7106)
            repository = SQLAlchemyMemoryRepository(session)
            record_a = await repository.save(_make_record(user_a, text="only for A"))
            await repository.save(_make_record(user_b, text="only for B"))
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMemoryRepository(session)
            relevant_a = await repository.find_relevant(user_a, limit=10)

        assert [record.id for record in relevant_a] == [record_a.id]


class TestListConfirmedByUser:
    async def test_returns_only_confirmed_without_limit(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 7007)
            repository = SQLAlchemyMemoryRepository(session)
            confirmed_records = [
                await repository.save(_make_record(user_id, text=f"confirmed {index}")) for index in range(12)
            ]
            await repository.save(_make_record(user_id, status=MemoryStatus.PENDING, text="pending"))
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMemoryRepository(session)
            listed = await repository.list_confirmed_by_user(user_id)

        assert len(listed) == 12
        assert {record.id for record in listed} == {record.id for record in confirmed_records}


class TestUpdateStatus:
    async def test_updates_status_and_updated_by(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 7008)
            repository = SQLAlchemyMemoryRepository(session)
            record = await repository.save(_make_record(user_id, status=MemoryStatus.PENDING))
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMemoryRepository(session)
            updated = await repository.update_status(record.id, MemoryStatus.REJECTED, updated_by="user")
            await session.commit()

        assert updated.status is MemoryStatus.REJECTED
        assert updated.updated_by == "user"
        assert updated.updated_at >= record.created_at

    async def test_raises_infrastructure_error_for_unknown_id(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            repository = SQLAlchemyMemoryRepository(session)
            with pytest.raises(InfrastructureError):
                await repository.update_status(uuid4(), MemoryStatus.CONFIRMED, updated_by="user")


class TestDeleteIsolatesUsers:
    """AC-2: `delete(record_id, user_id=B.id)` не удаляет запись пользователя A."""

    async def test_delete_by_owner_removes_record(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 7009)
            repository = SQLAlchemyMemoryRepository(session)
            record = await repository.save(_make_record(user_id))
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMemoryRepository(session)
            await repository.delete(record.id, user_id)
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMemoryRepository(session)
            assert await repository.get_by_id(record.id) is None

    async def test_delete_by_non_owner_does_not_remove_record(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            owner = await _persist_user(session, 7010)
            other_user = await _persist_user(session, 7110)
            repository = SQLAlchemyMemoryRepository(session)
            record = await repository.save(_make_record(owner))
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMemoryRepository(session)
            await repository.delete(record.id, other_user)
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMemoryRepository(session)
            still_there = await repository.get_by_id(record.id)

        assert still_there is not None
        assert still_there.id == record.id

    async def test_delete_of_unknown_id_is_idempotent(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 7011)
            repository = SQLAlchemyMemoryRepository(session)

            # Не должно поднимать исключение.
            await repository.delete(uuid4(), user_id)
            await session.commit()
