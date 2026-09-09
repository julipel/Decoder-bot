"""
ORM-модель таблицы `user_web_search_settings` (Infrastructure Layer,
внеспринтовая задача 2026-09-09) — прямой прецедент `user_active_models`
(`user_active_model_orm.py`, ADR-7.5).

Связь «пользователь → включён ли веб-поиск» — не доменная сущность с
собственным поведением (только атомарная замена значения), поэтому
таблица целиком инкапсулирована за `SQLAlchemyWebSearchSettingRepository`
и используется только там.

`user_id` — одновременно первичный и внешний ключ: ровно одна настройка
на пользователя, `set_enabled()` — upsert по этому ключу. Отсутствие
строки для пользователя означает «выключено» — это решает репозиторий
(`get_enabled` возвращает `False` при отсутствии записи), не эта модель.

Никаких `relationship()` — по тому же принципу, что и остальные
ORM-модели проекта (доступ только через явный SQL в репозитории).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from dekoder.infrastructure.persistence.base import Base


class UserWebSearchSettingORM(Base):
    """Строка таблицы `user_web_search_settings`: включён ли веб-поиск для одного пользователя."""

    __tablename__ = "user_web_search_settings"

    user_id: Mapped[UUID] = mapped_column(
        sa.Uuid(),
        sa.ForeignKey("users.id", name="fk_user_web_search_settings_user_id_users"),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
