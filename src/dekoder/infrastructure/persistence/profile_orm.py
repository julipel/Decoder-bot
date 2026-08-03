"""
ORM-модель таблицы `profiles` (Infrastructure Layer, задача S3-03).

Соответствует доменной сущности `dekoder.domain.profile.entities.
UserProfile`. Преобразование Domain↔ORM выполняется явно в
`infrastructure/persistence/mappers.py`.

`forbidden_phrasing` хранится как `sa.JSON` (список строк) — не как
строка с самодельным разделителем (backlog_3.md ADR-3.4, «Ограничения
хранения данных»). `status` хранится как обычная строка (`String`) с
явным `CheckConstraint` (`ck_profiles_status`), тем же способом, что и
`MessageORM.role`/`ck_messages_role` (S2-02) — доменный `ProfileStatus`
остаётся чистым Python `Enum` и не зависит от SQLAlchemy.

Частичный уникальный индекс `uq_profiles_is_default` защищает инвариант
«не более одного профиля-дефолта в каталоге» (backlog_3.md §5) на уровне
БД — по тому же образцу, что и `uq_conversations_active_user`
(`ConversationORM`, S2-02): `sqlite_where` ограничивает индекс строками
`is_default = 1`.

Никаких `relationship()` — каталог читается через `ProfileRepository`
(задача S3-05), не через ORM-навигацию.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from dekoder.infrastructure.persistence.base import Base


class ProfileORM(Base):
    """Строка таблицы `profiles`: запись общего сид-каталога профилей."""

    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(sa.Uuid(), primary_key=True)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    system_instruction: Mapped[str] = mapped_column(sa.Text, nullable=False)
    response_style: Mapped[str] = mapped_column(sa.Text, nullable=False)
    target_audience: Mapped[str] = mapped_column(sa.Text, nullable=False)
    formality_level: Mapped[str] = mapped_column(sa.Text, nullable=False)
    preferred_structure: Mapped[str] = mapped_column(sa.Text, nullable=False)
    forbidden_phrasing: Mapped[list[str]] = mapped_column(sa.JSON(), nullable=False)
    preferred_model: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    response_length_hint: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    additional_constraints: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    is_system: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    is_default: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_profiles_status"),
        sa.Index(
            "uq_profiles_is_default",
            "is_default",
            unique=True,
            sqlite_where=sa.text("is_default = 1"),
        ),
    )
