"""
Тесты преобразования Domain↔ORM (infrastructure/persistence/mappers.py,
задача S2-02) — round-trip без обращения к базе данных: сохранение UUID,
UTC-времени, роли и содержимого.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from dekoder.domain.conversation.entities import Conversation, Message, MessageRole
from dekoder.domain.user.entities import User
from dekoder.infrastructure.persistence.conversation_orm import ConversationORM
from dekoder.infrastructure.persistence.mappers import (
    conversation_to_domain,
    conversation_to_orm,
    message_to_domain,
    message_to_orm,
    user_to_domain,
    user_to_orm,
)
from dekoder.infrastructure.persistence.message_orm import MessageORM
from dekoder.infrastructure.persistence.user_orm import UserORM


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


class TestUserMapper:
    def test_round_trip_preserves_data(self) -> None:
        user_id = uuid4()
        created_at = _now()
        updated_at = created_at + timedelta(minutes=1)
        user = User(id=user_id, telegram_user_id=987654321, created_at=created_at, updated_at=updated_at)

        orm_user = user_to_orm(user)

        assert isinstance(orm_user, UserORM)
        assert orm_user.id == user_id
        assert orm_user.telegram_user_id == 987654321
        # Хранимое значение — naive UTC (SQLite не сохраняет offset), но
        # представляет тот же момент времени, что и исходный tz-aware datetime.
        assert orm_user.created_at.tzinfo is None
        assert orm_user.created_at == created_at.replace(tzinfo=None)

        round_tripped = user_to_domain(orm_user)

        assert round_tripped == user
        assert round_tripped.created_at.tzinfo is not None
        assert round_tripped.created_at == created_at

    def test_round_trip_preserves_non_utc_timezone_as_equivalent_instant(self) -> None:
        moscow_tz = timezone(timedelta(hours=3))
        created_at = datetime(2026, 1, 1, 15, 0, 0, tzinfo=moscow_tz)  # == 12:00 UTC
        user = User(id=uuid4(), telegram_user_id=1, created_at=created_at, updated_at=created_at)

        round_tripped = user_to_domain(user_to_orm(user))

        assert round_tripped.created_at == created_at
        assert round_tripped.created_at == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


class TestConversationMapper:
    def test_round_trip_preserves_active_conversation(self) -> None:
        conversation = Conversation(id=uuid4(), user_id=uuid4(), created_at=_now(), updated_at=_now(), closed_at=None)

        orm_conversation = conversation_to_orm(conversation)

        assert isinstance(orm_conversation, ConversationORM)
        assert orm_conversation.closed_at is None

        round_tripped = conversation_to_domain(orm_conversation)

        assert round_tripped == conversation
        assert round_tripped.is_active is True

    def test_round_trip_preserves_closed_conversation(self) -> None:
        created_at = _now()
        closed_at = created_at + timedelta(hours=2)
        conversation = Conversation(
            id=uuid4(), user_id=uuid4(), created_at=created_at, updated_at=closed_at, closed_at=closed_at
        )

        round_tripped = conversation_to_domain(conversation_to_orm(conversation))

        assert round_tripped == conversation
        assert round_tripped.closed_at == closed_at
        assert round_tripped.closed_at is not None
        assert round_tripped.closed_at.tzinfo is not None


class TestMessageMapper:
    def test_round_trip_preserves_user_message(self) -> None:
        message = Message(
            id=uuid4(),
            conversation_id=uuid4(),
            role=MessageRole.USER,
            content="Привет, Декодер!",
            created_at=_now(),
        )

        orm_message = message_to_orm(message)

        assert isinstance(orm_message, MessageORM)
        assert orm_message.role == "user"
        assert orm_message.content == "Привет, Декодер!"

        round_tripped = message_to_domain(orm_message)

        assert round_tripped == message
        assert round_tripped.role is MessageRole.USER

    def test_round_trip_preserves_assistant_message(self) -> None:
        message = Message(
            id=uuid4(),
            conversation_id=uuid4(),
            role=MessageRole.ASSISTANT,
            content="Привет! Чем помочь?",
            created_at=_now(),
        )

        orm_message = message_to_orm(message)
        assert orm_message.role == "assistant"

        round_tripped = message_to_domain(orm_message)

        assert round_tripped.role is MessageRole.ASSISTANT
        assert round_tripped.content == message.content
