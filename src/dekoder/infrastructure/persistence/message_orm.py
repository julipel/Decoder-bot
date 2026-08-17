"""
ORM-модель таблицы `messages` (Infrastructure Layer, задача S2-02).

Соответствует доменной сущности `dekoder.domain.conversation.entities.
Message`. Преобразование Domain↔ORM выполняется явно в
`infrastructure/persistence/mappers.py`.

`role` хранится как обычная строка (`String`) с явным `CheckConstraint`
(`ck_messages_role`), а не как `sqlalchemy.Enum` — доменный
`MessageRole` (`domain/conversation/entities.py`) остаётся чистым Python
Enum и не зависит от SQLAlchemy; конкретный способ ограничения набора
значений в БД — деталь Infrastructure Layer (backlog_2.md §7: «Domain
Layer не должен зависеть от SQLAlchemy Enum»).

`ck_messages_content_not_empty` использует `length(trim(content, ' ' ||
char(9) || char(10) || char(13))) > 0`, а не просто `trim(content)` —
SQLite `trim(X)` без второго аргумента обрезает только пробелы (0x20),
но НЕ табуляцию/переводы строк, поэтому строка из одних табов проходила
бы эту проверку как «непустая» (обнаружено вручную при реализации
задачи: интеграционный тест на content из табов падал без явного набора
символов). Второй аргумент `trim()` — набор символов для обрезки с обоих
концов; используются пробел, `\t` (`char(9)`), `\n` (`char(10)`), `\r`
(`char(13)`) — тот же набор, что и Python `str.strip()` покрывает для
типичного текста сообщений (полное совпадение с Unicode-пробелами
`str.strip()` не требуется — Sprint 2 работает с обычным текстом чата).

Никаких `relationship()` — история диалога запрашивается явно через
`MessageRepository` (следующая задача Sprint 2), не через ORM-навигацию.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from dekoder.infrastructure.persistence.base import Base


class MessageORM(Base):
    """Строка таблицы `messages`: диалог, роль, текст, время создания."""

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(sa.Uuid(), primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        sa.Uuid(),
        sa.ForeignKey("conversations.id", name="fk_messages_conversation_id_conversations"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
        sa.CheckConstraint(
            "length(trim(content, ' ' || char(9) || char(10) || char(13))) > 0",
            name="ck_messages_content_not_empty",
        ),
        sa.Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )
