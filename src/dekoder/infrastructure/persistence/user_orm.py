"""
ORM-модель таблицы `users` (Infrastructure Layer, задача S2-02).

Соответствует доменной сущности `dekoder.domain.user.entities.User`.
Преобразование Domain↔ORM выполняется явно в `infrastructure/persistence/
mappers.py` — эта модель не содержит бизнес-логики, не делает запросов и
не используется вне Infrastructure Layer (backlog_2.md §7/§15, инвариант 12).

Никаких `relationship()` — доступ к диалогам пользователя выполняется
через `ConversationRepository` (следующая задача Sprint 2), а не через
ORM-навигацию из `UserORM`.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from dekoder.infrastructure.persistence.base import Base


class UserORM(Base):
    """Строка таблицы `users`: внутренний id, telegram_user_id, таймстемпы."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(sa.Uuid(), primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (sa.UniqueConstraint("telegram_user_id", name="uq_users_telegram_user_id"),)
