"""
Явные функции преобразования Domain ↔ ORM (Infrastructure Layer, задача
S2-02) для `User`, `Conversation`, `Message`.

Не делают запросов, не коммитят, не грузят граф объектов — чистые
функции `ORM -> Domain` и `Domain -> ORM` (backlog_2.md §8: «ORM Model →
Mapper → Domain Entity» и обратно). Репозитории следующей задачи Sprint 2
будут вызывать эти функции, а не дублировать преобразование.

Отдельная забота — таймстемпы. Домен всегда оперирует timezone-aware UTC
`datetime` (задача требует «timezone-aware UTC на уровне Python»), но
SQLite не сохраняет offset: `DateTime(timezone=True)` на диалекте SQLite
всё равно возвращает *naive* `datetime` после round-trip через
`aiosqlite` (проверено вручную при реализации задачи). Поэтому mapper —
единственное место, которое явно снимает tzinfo перед записью
(`_to_naive_utc`, значение остаётся UTC по соглашению) и восстанавливает
`tzinfo=UTC` при чтении (`_to_aware_utc`), вместо того чтобы полагаться
на неявное поведение колонки.
"""

from __future__ import annotations

from datetime import UTC, datetime

from dekoder.domain.conversation.entities import Conversation, Message, MessageRole
from dekoder.domain.user.entities import User
from dekoder.infrastructure.persistence.conversation_orm import ConversationORM
from dekoder.infrastructure.persistence.message_orm import MessageORM
from dekoder.infrastructure.persistence.user_orm import UserORM


def _to_naive_utc(value: datetime) -> datetime:
    """Domain -> ORM: требует timezone-aware `datetime`, возвращает naive UTC для хранения."""
    if value.tzinfo is None:
        raise ValueError("Ожидается timezone-aware datetime (UTC)")
    return value.astimezone(UTC).replace(tzinfo=None)


def _to_aware_utc(value: datetime) -> datetime:
    """ORM -> Domain: naive datetime трактуется как UTC, tz-aware — приводится к UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def user_to_orm(user: User) -> UserORM:
    """Domain `User` -> `UserORM`."""
    return UserORM(
        id=user.id,
        telegram_user_id=user.telegram_user_id,
        created_at=_to_naive_utc(user.created_at),
        updated_at=_to_naive_utc(user.updated_at),
    )


def user_to_domain(orm_user: UserORM) -> User:
    """`UserORM` -> Domain `User`."""
    return User(
        id=orm_user.id,
        telegram_user_id=orm_user.telegram_user_id,
        created_at=_to_aware_utc(orm_user.created_at),
        updated_at=_to_aware_utc(orm_user.updated_at),
    )


def conversation_to_orm(conversation: Conversation) -> ConversationORM:
    """Domain `Conversation` -> `ConversationORM`."""
    return ConversationORM(
        id=conversation.id,
        user_id=conversation.user_id,
        created_at=_to_naive_utc(conversation.created_at),
        updated_at=_to_naive_utc(conversation.updated_at),
        closed_at=_to_naive_utc(conversation.closed_at) if conversation.closed_at is not None else None,
    )


def conversation_to_domain(orm_conversation: ConversationORM) -> Conversation:
    """`ConversationORM` -> Domain `Conversation`."""
    return Conversation(
        id=orm_conversation.id,
        user_id=orm_conversation.user_id,
        created_at=_to_aware_utc(orm_conversation.created_at),
        updated_at=_to_aware_utc(orm_conversation.updated_at),
        closed_at=_to_aware_utc(orm_conversation.closed_at) if orm_conversation.closed_at is not None else None,
    )


def message_to_orm(message: Message) -> MessageORM:
    """Domain `Message` -> `MessageORM`."""
    return MessageORM(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role.value,
        content=message.content,
        created_at=_to_naive_utc(message.created_at),
    )


def message_to_domain(orm_message: MessageORM) -> Message:
    """`MessageORM` -> Domain `Message`."""
    return Message(
        id=orm_message.id,
        conversation_id=orm_message.conversation_id,
        role=MessageRole(orm_message.role),
        content=orm_message.content,
        created_at=_to_aware_utc(orm_message.created_at),
    )
