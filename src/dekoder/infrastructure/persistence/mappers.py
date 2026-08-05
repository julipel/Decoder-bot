"""
Явные функции преобразования Domain ↔ ORM (Infrastructure Layer, задача
S2-02) для `User`, `Conversation`, `Message`, (задача S3-03) для
`UserProfile`, и (Sprint 5, задача S5-04) для `MemoryRecord`.

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

`user_active_profiles` (`UserActiveProfileORM`, задача S3-03) намеренно
не получает `*_to_domain`/`*_to_orm` здесь — это не доменная сущность
(ADR-3.1), только внутренняя связь «пользователь → активный профиль»,
которую `SQLAlchemyProfileRepository` (задача S3-05) читает/пишет
напрямую.
"""

from __future__ import annotations

from datetime import UTC, datetime

from dekoder.domain.conversation.entities import Conversation, Message, MessageRole
from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import (
    MemoryCategory,
    MemoryConfidence,
    MemorySource,
    MemoryStatus,
)
from dekoder.domain.profile.entities import UserProfile
from dekoder.domain.profile.value_objects import ProfileStatus
from dekoder.domain.user.entities import User
from dekoder.infrastructure.persistence.conversation_orm import ConversationORM
from dekoder.infrastructure.persistence.memory_record_orm import MemoryRecordORM
from dekoder.infrastructure.persistence.message_orm import MessageORM
from dekoder.infrastructure.persistence.profile_orm import ProfileORM
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


def profile_to_orm(profile: UserProfile) -> ProfileORM:
    """Domain `UserProfile` -> `ProfileORM`."""
    return ProfileORM(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        system_instruction=profile.system_instruction,
        response_style=profile.response_style,
        target_audience=profile.target_audience,
        formality_level=profile.formality_level,
        preferred_structure=profile.preferred_structure,
        forbidden_phrasing=list(profile.forbidden_phrasing),
        preferred_model=profile.preferred_model.value if profile.preferred_model is not None else None,
        response_length_hint=profile.response_length_hint,
        additional_constraints=profile.additional_constraints,
        status=profile.status.value,
        is_system=profile.is_system,
        is_default=profile.is_default,
        created_at=_to_naive_utc(profile.created_at),
        updated_at=_to_naive_utc(profile.updated_at),
    )


def profile_to_domain(orm_profile: ProfileORM) -> UserProfile:
    """`ProfileORM` -> Domain `UserProfile`."""
    return UserProfile(
        id=orm_profile.id,
        name=orm_profile.name,
        description=orm_profile.description,
        system_instruction=orm_profile.system_instruction,
        response_style=orm_profile.response_style,
        target_audience=orm_profile.target_audience,
        formality_level=orm_profile.formality_level,
        preferred_structure=orm_profile.preferred_structure,
        forbidden_phrasing=tuple(orm_profile.forbidden_phrasing),
        preferred_model=ModelId(orm_profile.preferred_model) if orm_profile.preferred_model is not None else None,
        response_length_hint=orm_profile.response_length_hint,
        additional_constraints=orm_profile.additional_constraints,
        status=ProfileStatus(orm_profile.status),
        is_system=orm_profile.is_system,
        is_default=orm_profile.is_default,
        created_at=_to_aware_utc(orm_profile.created_at),
        updated_at=_to_aware_utc(orm_profile.updated_at),
    )


def memory_record_to_orm(record: MemoryRecord) -> MemoryRecordORM:
    """Domain `MemoryRecord` -> `MemoryRecordORM`."""
    return MemoryRecordORM(
        id=record.id,
        user_id=record.user_id,
        text=record.text,
        category=record.category.value,
        source=record.source.value,
        status=record.status.value,
        confidence=record.confidence.value,
        is_sensitive=record.is_sensitive,
        expires_at=_to_naive_utc(record.expires_at) if record.expires_at is not None else None,
        updated_by=record.updated_by,
        created_at=_to_naive_utc(record.created_at),
        updated_at=_to_naive_utc(record.updated_at),
    )


def memory_record_to_domain(orm_record: MemoryRecordORM) -> MemoryRecord:
    """`MemoryRecordORM` -> Domain `MemoryRecord`."""
    return MemoryRecord(
        id=orm_record.id,
        user_id=orm_record.user_id,
        text=orm_record.text,
        category=MemoryCategory(orm_record.category),
        source=MemorySource(orm_record.source),
        status=MemoryStatus(orm_record.status),
        confidence=MemoryConfidence(orm_record.confidence),
        is_sensitive=orm_record.is_sensitive,
        expires_at=_to_aware_utc(orm_record.expires_at) if orm_record.expires_at is not None else None,
        updated_by=orm_record.updated_by,
        created_at=_to_aware_utc(orm_record.created_at),
        updated_at=_to_aware_utc(orm_record.updated_at),
    )
