"""create profiles user_active_profiles

Первая схемная миграция Sprint 3 (задача S3-03): таблицы `profiles` и
`user_active_profiles`, описанные в backlog_3.md §5.

Сгенерирована `alembic revision --autogenerate` (против временной базы,
поднятой до ревизии `a96ab72bfa8a`) и вручную выверена и дополнена
комментариями — autogenerate верно распознал `CHECK`-ограничение
(`ck_profiles_status`), внешние ключи `user_active_profiles` и частичный
уникальный индекс (`uq_profiles_is_default`, `sqlite_where`), но порядок
операций переставлен вручную под явное требование задачи: `upgrade` —
`profiles` → `user_active_profiles` → индекс; `downgrade` — строго в
обратном порядке (сначала индекс, затем таблицы `user_active_profiles` →
`profiles`).

Сид-данные (2-4 профиля каталога) в эту миграцию не входят — отдельная
ревизия S3-04 (ADR-3.4: сид-данные — отдельная data migration после
схемной).

Revision ID: 14bf7e3ae815
Revises: a96ab72bfa8a
Create Date: 2026-08-03 16:21:01.388772

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "14bf7e3ae815"
down_revision: str | Sequence[str] | None = "a96ab72bfa8a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт таблицы profiles → user_active_profiles, затем частичный уникальный индекс."""
    op.create_table(
        "profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("system_instruction", sa.Text(), nullable=False),
        sa.Column("response_style", sa.Text(), nullable=False),
        sa.Column("target_audience", sa.Text(), nullable=False),
        sa.Column("formality_level", sa.Text(), nullable=False),
        sa.Column("preferred_structure", sa.Text(), nullable=False),
        sa.Column("forbidden_phrasing", sa.JSON(), nullable=False),
        sa.Column("preferred_model", sa.Text(), nullable=True),
        sa.Column("response_length_hint", sa.Text(), nullable=True),
        sa.Column("additional_constraints", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_profiles_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "user_active_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_active_profiles_user_id_users"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], name="fk_user_active_profiles_profile_id_profiles"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # Частичный уникальный индекс — единственная защита инварианта «не более
    # одного профиля-дефолта в каталоге» на уровне БД, по тому же образцу,
    # что и uq_conversations_active_user (S2-02).
    op.create_index(
        "uq_profiles_is_default",
        "profiles",
        ["is_default"],
        unique=True,
        sqlite_where=sa.text("is_default = 1"),
    )


def downgrade() -> None:
    """Удаляет частичный уникальный индекс, затем таблицы user_active_profiles → profiles."""
    op.drop_index("uq_profiles_is_default", table_name="profiles", sqlite_where=sa.text("is_default = 1"))

    op.drop_table("user_active_profiles")
    op.drop_table("profiles")
