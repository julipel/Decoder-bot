"""create user_active_models

Схемная миграция персонального выбора AI-модели (Sprint 7, задача S7-04,
ADR-7.5, `backlog_7.md` §5): таблица `user_active_models` — прямой
прецедент `user_active_profiles` (S3-03, ADR-3.1): `user_id` одновременно
первичный и внешний ключ (ровно один активный выбор на пользователя),
`select()` (`SQLAlchemyModelSelectionRepository`) — upsert по этому ключу.

Как и `memory_records`/`knowledge_documents` (Sprint 5/6) — только
схемная миграция, без сид-данных (ADR-7.5): `user_active_models`
заполняется исключительно через Telegram-команду `/model` (S7-07), не
через bootstrap-сидер.

`model_id` хранится как обычная строка, без FK на каталог моделей —
каталог статичный файловый (ADR-7.4), не имеет представления в БД.

Сгенерирована `alembic revision --autogenerate` (против БД, поднятой до
ревизии `82d9884e32a2`) и вручную выверена/дополнена комментариями —
autogenerate верно распознал колонки, внешний ключ и первичный ключ без
дополнительной правки.

Revision ID: ed5701d2f683
Revises: 82d9884e32a2
Create Date: 2026-08-06 22:54:49.169304

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ed5701d2f683"
down_revision: str | Sequence[str] | None = "82d9884e32a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт таблицу user_active_models."""
    op.create_table(
        "user_active_models",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_active_models_user_id_users"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    """Удаляет таблицу user_active_models."""
    op.drop_table("user_active_models")
