"""
ORM-модель таблицы `memory_records` (Infrastructure Layer, Sprint 5,
задача S5-04, ADR-5.7, `backlog_5.md` §5).

Соответствует доменной сущности `dekoder.domain.memory.entities.
MemoryRecord`. Преобразование Domain↔ORM выполняется явно в
`infrastructure/persistence/mappers.py`.

`category`/`source`/`status`/`confidence` хранятся как обычные строки
(`sa.String`) с явными `CheckConstraint`, тем же способом, что и
`ProfileORM.status`/`MessageORM.role` — доменные enum'ы (`domain/memory/
value_objects.py`) остаются чистым Python `Enum` и не зависят от
SQLAlchemy.

В отличие от `profiles` (сид-каталог), `memory_records` — исключительно
пользовательские данные, поэтому здесь нет `is_default`/`is_system`,
только владелец (`user_id`, FK → `users.id`).

Индекс `(user_id, status)` ускоряет `find_relevant`/`list_confirmed_by_user`
(ADR-5.6/5.7) — обе операции фильтруют строго по этой паре колонок.

Никаких `relationship()` — по тому же принципу, что и остальные
ORM-модели Sprint 2–4 (доступ только через явный SQL в репозитории).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from dekoder.infrastructure.persistence.base import Base


class MemoryRecordORM(Base):
    """Строка таблицы `memory_records`: одна подтверждённая/ожидающая/отклонённая запись памяти пользователя."""

    __tablename__ = "memory_records"

    id: Mapped[UUID] = mapped_column(sa.Uuid(), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid(),
        sa.ForeignKey("users.id", name="fk_memory_records_user_id_users"),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    category: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    source: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    confidence: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    updated_by: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        sa.CheckConstraint(
            "category IN ('personal', 'preference', 'fact', 'other')",
            name="ck_memory_records_category",
        ),
        sa.CheckConstraint(
            "source IN ('user_explicit', 'admin', 'inferred')",
            name="ck_memory_records_source",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected')",
            name="ck_memory_records_status",
        ),
        sa.CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="ck_memory_records_confidence",
        ),
        sa.Index("ix_memory_records_user_status", "user_id", "status"),
    )
