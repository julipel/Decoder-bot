"""
ORM-модель таблицы `user_active_profiles` (Infrastructure Layer, задача
S3-03, ADR-3.1).

Связь «пользователь → активный профиль» — не доменная сущность (ADR-3.1:
«у связи нет собственного поведения, только атомарная замена
значения»), поэтому у неё нет соответствующей записи в `domain/profile/`
и нет функции `*_to_domain`/`*_to_orm` в `mappers.py` — таблица целиком
инкапсулирована за `ProfileRepository` (задача S3-05) и используется
только там.

`user_id` — одновременно первичный и внешний ключ: ровно одна активная
запись на пользователя, `select_profile` (задача S3-05) — upsert по
этому ключу. Нет отдельного суррогатного `id` — он не нужен ни одному
запросу.

Никаких `relationship()` — по тому же принципу, что и остальные
ORM-модели Sprint 2/3 (доступ только через явный SQL в репозитории).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from dekoder.infrastructure.persistence.base import Base


class UserActiveProfileORM(Base):
    """Строка таблицы `user_active_profiles`: текущий выбор профиля одного пользователя."""

    __tablename__ = "user_active_profiles"

    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid(),
        sa.ForeignKey("users.id", name="fk_user_active_profiles_user_id_users"),
        primary_key=True,
    )
    profile_id: Mapped[UUID] = mapped_column(
        sa.Uuid(),
        sa.ForeignKey("profiles.id", name="fk_user_active_profiles_profile_id_profiles"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
