"""
ORM-модель таблицы `conversations` (Infrastructure Layer, задача S2-02).

Соответствует доменной сущности `dekoder.domain.conversation.entities.
Conversation`. Преобразование Domain↔ORM выполняется явно в
`infrastructure/persistence/mappers.py`.

Частичный уникальный индекс `uq_conversations_active_user` защищает
инвариант «у пользователя не более одного активного диалога»
(backlog_2.md §7) на уровне БД: обычный `UNIQUE(user_id, closed_at)`
недостаточен, поскольку SQL допускает несколько строк с `NULL` в
уникальном составном индексе. `sqlite_where` — диалект-специфичный
параметр SQLAlchemy `Index` для SQLite (`CREATE UNIQUE INDEX ... WHERE
closed_at IS NULL`); Sprint 2 использует только SQLite (backlog_2.md §3),
поэтому других `*_where`-вариантов здесь нет.

Никаких `relationship()` на `messages` — история диалога не должна
загружаться автоматически вместе с `Conversation` (задача явно требует
избегать `lazy="joined"` на коллекции сообщений); доступ — через
`MessageRepository` (следующая задача Sprint 2). ORM-каскады тоже не
используются — команда `/clear` (следующая задача) удаляет сообщения
явным запросом репозитория, а не каскадным удалением диалога.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from dekoder.infrastructure.persistence.base import Base


class ConversationORM(Base):
    """Строка таблицы `conversations`: владелец, таймстемпы, `closed_at`."""

    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(sa.Uuid(), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid(),
        sa.ForeignKey("users.id", name="fk_conversations_user_id_users"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        sa.Index("ix_conversations_user_id", "user_id"),
        sa.Index(
            "uq_conversations_active_user",
            "user_id",
            unique=True,
            sqlite_where=sa.text("closed_at IS NULL"),
        ),
    )
