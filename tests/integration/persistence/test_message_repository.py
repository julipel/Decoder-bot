"""
Интеграционные тесты `SQLAlchemyMessageRepository` (задача S2-05) на
временной SQLite-базе (`tmp_path` — НЕ рабочая БД). Стиль fixture'ов — как
в `tests/integration/persistence/test_conversation_repository.py`.

Ключевые тесты:
- `TestForeignKeyEnforcement` — попытка сохранить сообщение с
  несуществующим `conversation_id` должна быть отклонена БД (внешний ключ
  `messages.conversation_id → conversations.id`, S2-02), запись не
  создаётся.
- `TestClear` — `clear()` реально удаляет строки из БД (проверено прямым
  `COUNT`), не трогает сам `Conversation` (запись остаётся, `closed_at`
  не меняется).
- `TestHistoryOrdering` — стабильность сортировки `created_at ASC, id ASC`
  при искусственно одинаковых `created_at`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from dekoder.domain.conversation.entities import Message, MessageRole
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.conversation_orm import ConversationORM
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.message_orm import MessageORM
from dekoder.infrastructure.persistence.message_repository import SQLAlchemyMessageRepository
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.infrastructure.persistence.user_orm import UserORM
from dekoder.shared.errors import InfrastructureError


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'message-repository.db'}"
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
    """Создаёт пользователя напрямую через ORM (репозиторий пользователей — вне области S2-05)."""
    now = _now()
    user = UserORM(id=uuid4(), telegram_user_id=telegram_user_id, created_at=now, updated_at=now)
    session.add(user)
    await session.commit()
    return user.id


async def _persist_conversation(session: AsyncSession, user_id: UUID) -> UUID:
    """Создаёт диалог напрямую через ORM (репозиторий диалогов — вне области S2-05)."""
    now = _now()
    conversation = ConversationORM(id=uuid4(), user_id=user_id, created_at=now, updated_at=now, closed_at=None)
    session.add(conversation)
    await session.commit()
    return conversation.id


def _make_message(
    conversation_id: UUID,
    *,
    role: MessageRole = MessageRole.USER,
    content: str = "hello",
    created_at: datetime | None = None,
    message_id: UUID | None = None,
) -> Message:
    return Message(
        id=message_id or uuid4(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        created_at=created_at or _now(),
    )


class TestSaveAndHistory:
    async def test_save_user_and_assistant_messages_round_trip_all_fields_via_history(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 6001)
            conversation_id = await _persist_conversation(session, user_id)
            repository = SQLAlchemyMessageRepository(session)

            user_message = _make_message(conversation_id, role=MessageRole.USER, content="Привет, бот!")
            assistant_message = _make_message(
                conversation_id,
                role=MessageRole.ASSISTANT,
                content="Привет! Чем помочь?",
                created_at=_now() + timedelta(seconds=5),
            )
            await repository.save(user_message)
            await repository.save(assistant_message)
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMessageRepository(session)
            history = await repository.history(conversation_id)

        assert history == [user_message, assistant_message]
        assert history[0].id == user_message.id
        assert history[0].conversation_id == conversation_id
        assert history[0].role == MessageRole.USER
        assert history[0].content == "Привет, бот!"
        assert history[0].created_at == user_message.created_at
        assert history[1].role == MessageRole.ASSISTANT
        assert history[1].content == "Привет! Чем помочь?"
        assert isinstance(history[0], Message)
        assert not isinstance(history[0], MessageORM)

    async def test_history_is_empty_for_freshly_created_conversation(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 6002)
            conversation_id = await _persist_conversation(session, user_id)
            repository = SQLAlchemyMessageRepository(session)

            history = await repository.history(conversation_id)

        assert history == []

    async def test_history_is_isolated_between_two_conversations(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            # Два разных пользователя — у каждого не более одного активного
            # диалога (`uq_conversations_active_user`, S2-02), поэтому для
            # проверки изоляции истории между диалогами используются два
            # владельца, а не два активных диалога одного пользователя.
            user_a = await _persist_user(session, 6003)
            user_b = await _persist_user(session, 6103)
            conversation_a = await _persist_conversation(session, user_a)
            conversation_b = await _persist_conversation(session, user_b)
            repository = SQLAlchemyMessageRepository(session)

            message_a = await repository.save(_make_message(conversation_a, content="only in A"))
            message_b = await repository.save(_make_message(conversation_b, content="only in B"))
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMessageRepository(session)
            history_a = await repository.history(conversation_a)
            history_b = await repository.history(conversation_b)

        assert history_a == [message_a]
        assert history_b == [message_b]


class TestForeignKeyEnforcement:
    async def test_save_with_unknown_conversation_id_raises_infrastructure_error_and_persists_nothing(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        unknown_conversation_id = uuid4()
        async with session_factory() as session:
            repository = SQLAlchemyMessageRepository(session)
            with pytest.raises(InfrastructureError):
                await repository.save(_make_message(unknown_conversation_id))

        async with session_factory() as session:
            rows = (
                (await session.execute(select(MessageORM).where(MessageORM.conversation_id == unknown_conversation_id)))
                .scalars()
                .all()
            )
        assert rows == []


class TestClear:
    async def test_clear_deletes_rows_from_the_database_and_leaves_conversation_untouched(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 6004)
            conversation_id = await _persist_conversation(session, user_id)
            repository = SQLAlchemyMessageRepository(session)
            await repository.save(_make_message(conversation_id, content="1"))
            await repository.save(_make_message(conversation_id, content="2"))
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMessageRepository(session)
            deleted_count = await repository.clear(conversation_id)
            await session.commit()

        assert deleted_count == 2

        async with session_factory() as session:
            row_count = await session.scalar(
                select(func.count()).select_from(MessageORM).where(MessageORM.conversation_id == conversation_id)
            )
            conversation = await session.get(ConversationORM, conversation_id)

        assert row_count == 0
        assert conversation is not None
        assert conversation.closed_at is None

    async def test_clear_only_removes_messages_of_the_target_conversation(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            # Два разных пользователя — по той же причине, что и в
            # `test_history_is_isolated_between_two_conversations`.
            user_a = await _persist_user(session, 6005)
            user_b = await _persist_user(session, 6105)
            conversation_a = await _persist_conversation(session, user_a)
            conversation_b = await _persist_conversation(session, user_b)
            repository = SQLAlchemyMessageRepository(session)
            await repository.save(_make_message(conversation_a, content="a"))
            other_message = await repository.save(_make_message(conversation_b, content="b"))
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMessageRepository(session)
            deleted_count = await repository.clear(conversation_a)
            await session.commit()

        assert deleted_count == 1

        async with session_factory() as session:
            repository = SQLAlchemyMessageRepository(session)
            history_a = await repository.history(conversation_a)
            history_b = await repository.history(conversation_b)

        assert history_a == []
        assert history_b == [other_message]

    async def test_clear_on_empty_history_is_idempotent_and_returns_zero(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 6006)
            conversation_id = await _persist_conversation(session, user_id)
            repository = SQLAlchemyMessageRepository(session)

            first_call = await repository.clear(conversation_id)
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMessageRepository(session)
            second_call = await repository.clear(conversation_id)
            await session.commit()

        assert first_call == 0
        assert second_call == 0


class TestHistoryOrdering:
    async def test_ordering_is_deterministic_by_id_when_created_at_ties(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            user_id = await _persist_user(session, 6007)
            conversation_id = await _persist_conversation(session, user_id)
            repository = SQLAlchemyMessageRepository(session)

            same_timestamp = _now()
            # Идентификаторы намеренно не связаны с порядком создания.
            id_high = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
            id_low = UUID("00000000-0000-0000-0000-000000000000")
            message_high_id = _make_message(
                conversation_id, content="high-id", created_at=same_timestamp, message_id=id_high
            )
            message_low_id = _make_message(
                conversation_id, content="low-id", created_at=same_timestamp, message_id=id_low
            )
            # Сохраняем сообщение с большим id первым, чтобы порядок вставки
            # не мог случайно совпасть с ожидаемым порядком сортировки.
            await repository.save(message_high_id)
            await repository.save(message_low_id)
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyMessageRepository(session)
            history = await repository.history(conversation_id)

        assert [message.id for message in history] == [id_low, id_high]
