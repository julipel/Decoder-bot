"""
ORM-модель таблицы `user_active_models` (Infrastructure Layer, Sprint 7,
задача S7-04, ADR-7.5) — прямой прецедент `user_active_profiles`
(`user_active_profile_orm.py`, ADR-3.1).

Связь «пользователь → выбранная модель» — не доменная сущность с
собственным поведением (только атомарная замена значения), поэтому
таблица целиком инкапсулирована за `SQLAlchemyModelSelectionRepository`
(задача S7-04) и используется только там.

`user_id` — одновременно первичный и внешний ключ: ровно один активный
выбор на пользователя, `select()` (задача S7-04) — upsert по этому ключу.
Нет отдельного суррогатного `id` — он не нужен ни одному запросу.

`model_id` хранится как обычная строка (`sa.String`), без FK на
какую-либо таблицу каталога моделей — каталог статичный файловый (ADR-7.4),
не имеет представления в БД, поэтому ссылочную целостность здесь
обеспечить нечем; проверка «модель существует и доступна» выполняется на
уровне use case'а (`SelectModel`, ADR-7.9), не БД.

Никаких `relationship()` — по тому же принципу, что и остальные
ORM-модели Sprint 2–6 (доступ только через явный SQL в репозитории).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from dekoder.infrastructure.persistence.base import Base


class UserActiveModelORM(Base):
    """Строка таблицы `user_active_models`: текущий персональный выбор AI-модели одного пользователя."""

    __tablename__ = "user_active_models"

    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid(),
        sa.ForeignKey("users.id", name="fk_user_active_models_user_id_users"),
        primary_key=True,
    )
    model_id: Mapped[str] = mapped_column(sa.String(length=128), nullable=False)
    selected_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
