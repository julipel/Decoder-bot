"""
Интеграционные тесты ORM-моделей `UserORM`/`ConversationORM`/`MessageORM`
(задача S2-02) и `ProfileORM`/`UserActiveProfileORM` (задача S3-03) на
временной SQLite-базе (`tmp_path` — НЕ рабочая БД): уникальность
`telegram_user_id`, внешние ключи, CHECK-ограничения и частичные
уникальные индексы (активный диалог пользователя, профиль-дефолт
каталога).

Схема создаётся через `Base.metadata.create_all()` — единственное
допустимое исключение для тестового окружения (backlog_2.md §3, «Прямое
создание таблиц средствами SQLAlchemy... запрещено, за исключением
тестового окружения»); рабочее приложение создаёт схему исключительно
через Alembic (см. `tests/integration/persistence/test_migrations.py`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.conversation_orm import ConversationORM
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.message_orm import MessageORM
from dekoder.infrastructure.persistence.profile_orm import ProfileORM
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.infrastructure.persistence.user_active_profile_orm import UserActiveProfileORM
from dekoder.infrastructure.persistence.user_orm import UserORM


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _make_user(telegram_user_id: int, *, user_id: UUID | None = None) -> UserORM:
    now = _now()
    return UserORM(id=user_id or uuid4(), telegram_user_id=telegram_user_id, created_at=now, updated_at=now)


def _make_conversation(user_id: UUID, *, closed_at: datetime | None = None) -> ConversationORM:
    now = _now()
    return ConversationORM(
        id=uuid4(), user_id=user_id, created_at=now, updated_at=closed_at or now, closed_at=closed_at
    )


def _make_message(conversation_id: UUID, *, role: str = "user", content: str = "текст") -> MessageORM:
    return MessageORM(id=uuid4(), conversation_id=conversation_id, role=role, content=content, created_at=_now())


def _make_profile(
    *,
    status: str = "active",
    is_default: bool = False,
    name: str = "Профиль",
) -> ProfileORM:
    now = _now()
    return ProfileORM(
        id=uuid4(),
        name=name,
        description="Описание профиля.",
        system_instruction="Отвечай по делу.",
        response_style="нейтральный",
        target_audience="широкая аудитория",
        formality_level="нейтральный",
        preferred_structure="без особых требований",
        forbidden_phrasing=[],
        preferred_model=None,
        response_length_hint=None,
        additional_constraints="",
        status=status,
        is_system=True,
        is_default=is_default,
        created_at=now,
        updated_at=now,
    )


def _make_user_active_profile(user_id: UUID, profile_id: UUID) -> UserActiveProfileORM:
    return UserActiveProfileORM(user_id=user_id, profile_id=profile_id, updated_at=_now())


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'orm-constraints.db'}"
    test_engine = create_database_engine(database_url)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker:  # type: ignore[type-arg]
    return create_session_factory(engine)


class TestUserPersistence:
    async def test_creates_user(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            session.add(_make_user(111))
            await session.commit()

        async with session_factory() as session:
            stored = (await session.execute(select(UserORM).where(UserORM.telegram_user_id == 111))).scalar_one()
            assert stored.telegram_user_id == 111

    async def test_duplicate_telegram_user_id_is_rejected(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            session.add(_make_user(222))
            await session.commit()

        async with session_factory() as session:
            session.add(_make_user(222))
            with pytest.raises(IntegrityError):
                await session.commit()


class TestForeignKeyEnforcement:
    async def test_conversation_with_unknown_user_is_rejected(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            session.add(_make_conversation(uuid4()))
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_message_with_unknown_conversation_is_rejected(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            session.add(_make_message(uuid4()))
            with pytest.raises(IntegrityError):
                await session.commit()


class TestMessageCheckConstraints:
    async def _persisted_conversation_id(self, session_factory: async_sessionmaker) -> UUID:  # type: ignore[type-arg]
        async with session_factory() as session:
            user = _make_user(333)
            session.add(user)
            await session.flush()
            conversation = _make_conversation(user.id)
            session.add(conversation)
            await session.commit()
            return conversation.id

    async def test_unknown_role_is_rejected(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        conversation_id = await self._persisted_conversation_id(session_factory)

        async with session_factory() as session:
            session.add(_make_message(conversation_id, role="system"))
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_empty_content_is_rejected(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        conversation_id = await self._persisted_conversation_id(session_factory)

        async with session_factory() as session:
            session.add(_make_message(conversation_id, content=""))
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_whitespace_only_content_is_rejected(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        conversation_id = await self._persisted_conversation_id(session_factory)

        async with session_factory() as session:
            session.add(_make_message(conversation_id, content="   \t  "))
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_valid_user_and_assistant_roles_are_accepted(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        conversation_id = await self._persisted_conversation_id(session_factory)

        async with session_factory() as session:
            session.add(_make_message(conversation_id, role="user"))
            session.add(_make_message(conversation_id, role="assistant"))
            await session.commit()


class TestActiveConversationUniqueness:
    """
    Ключевой тест задачи S2-02: инвариант «не более одного активного
    диалога на пользователя» должен защищаться частичным уникальным
    индексом `uq_conversations_active_user` на уровне БД, а не только
    проверкой на уровне Python (backlog_2.md §7).
    """

    async def test_second_active_conversation_violates_database_constraint(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user = _make_user(444)
            session.add(user)
            await session.commit()
            user_id = user.id

        # Первый активный диалог создаётся успешно.
        async with session_factory() as session:
            first_active = _make_conversation(user_id)
            session.add(first_active)
            await session.commit()
            first_active_id = first_active.id

        # Попытка создать второй активный диалог для того же пользователя
        # должна упасть на уровне БД (IntegrityError), а не пройти молча.
        async with session_factory() as session:
            second_active = _make_conversation(user_id)
            session.add(second_active)
            with pytest.raises(IntegrityError):
                await session.commit()

        # Закрываем первый диалог...
        async with session_factory() as session:
            stored_first = await session.get(ConversationORM, first_active_id)
            assert stored_first is not None
            stored_first.closed_at = _now() + timedelta(hours=1)
            await session.commit()

        # ...теперь создание нового активного диалога проходит успешно.
        async with session_factory() as session:
            third_active = _make_conversation(user_id)
            session.add(third_active)
            await session.commit()
            third_active_id = third_active.id

        async with session_factory() as session:
            active_conversations = (
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
            assert [c.id for c in active_conversations] == [third_active_id]


class TestProfileCheckConstraint:
    async def test_unknown_status_is_rejected(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            session.add(_make_profile(status="draft"))
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_valid_active_and_archived_status_are_accepted(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            session.add(_make_profile(status="active", name="Активный"))
            session.add(_make_profile(status="archived", name="Архивный"))
            await session.commit()


class TestProfileDefaultUniqueness:
    """
    Ключевой тест задачи S3-03: инвариант «не более одного профиля-дефолта
    в каталоге» должен защищаться частичным уникальным индексом
    `uq_profiles_is_default` на уровне БД (backlog_3.md §5, ADR-3.4).
    """

    async def test_second_default_profile_violates_database_constraint(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            session.add(_make_profile(is_default=True, name="Первый дефолт"))
            await session.commit()

        async with session_factory() as session:
            session.add(_make_profile(is_default=True, name="Второй дефолт"))
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_multiple_non_default_profiles_are_accepted(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            session.add(_make_profile(is_default=False, name="Первый"))
            session.add(_make_profile(is_default=False, name="Второй"))
            await session.commit()


class TestUserActiveProfileForeignKeyEnforcement:
    async def test_unknown_user_id_is_rejected(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            profile = _make_profile()
            session.add(profile)
            await session.commit()
            profile_id = profile.id

        async with session_factory() as session:
            session.add(_make_user_active_profile(uuid4(), profile_id))
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_unknown_profile_id_is_rejected(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            user = _make_user(555)
            session.add(user)
            await session.commit()
            user_id = user.id

        async with session_factory() as session:
            session.add(_make_user_active_profile(user_id, uuid4()))
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_valid_selection_is_accepted(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            user = _make_user(666)
            profile = _make_profile()
            session.add(user)
            session.add(profile)
            await session.commit()
            user_id, profile_id = user.id, profile.id

        async with session_factory() as session:
            session.add(_make_user_active_profile(user_id, profile_id))
            await session.commit()

        async with session_factory() as session:
            stored = await session.get(UserActiveProfileORM, user_id)
            assert stored is not None
            assert stored.profile_id == profile_id
