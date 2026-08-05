"""create memory_records

Схемная миграция долговременной памяти (Sprint 5, задача S5-04,
ADR-5.7, `backlog_5.md` §5): таблица `memory_records` и индекс
`(user_id, status)`, ускоряющий `find_relevant`/`list_confirmed_by_user`
(ADR-5.6).

В отличие от `profiles` (S3-03/S3-04, схема + отдельная сид-миграция),
`memory_records` — исключительно пользовательские данные, создаваемые
через `/remember` (ADR-5.7): здесь нет и не будет сид-миграции.

Revision ID: 161899ea36c0
Revises: 27c4e9f2a103
Create Date: 2026-08-05 10:43:13.276193

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "161899ea36c0"
down_revision: str | Sequence[str] | None = "27c4e9f2a103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт таблицу memory_records, затем индекс (user_id, status)."""
    op.create_table(
        "memory_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('personal', 'preference', 'fact', 'other')", name="ck_memory_records_category"
        ),
        sa.CheckConstraint("source IN ('user_explicit', 'admin', 'inferred')", name="ck_memory_records_source"),
        sa.CheckConstraint("status IN ('pending', 'confirmed', 'rejected')", name="ck_memory_records_status"),
        sa.CheckConstraint("confidence IN ('low', 'medium', 'high')", name="ck_memory_records_confidence"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_memory_records_user_id_users"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_memory_records_user_status",
        "memory_records",
        ["user_id", "status"],
    )


def downgrade() -> None:
    """Удаляет индекс (user_id, status), затем таблицу memory_records."""
    op.drop_index("ix_memory_records_user_status", table_name="memory_records")
    op.drop_table("memory_records")
