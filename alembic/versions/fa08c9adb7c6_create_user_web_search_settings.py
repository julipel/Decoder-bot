"""create user web search settings

Схемная миграция персонального переключателя веб-поиска (внеспринтовая
задача, 2026-09-09) — таблица `user_web_search_settings`, прямой
прецедент `user_active_models` (S7-04, ADR-7.5): `user_id` одновременно
первичный и внешний ключ (ровно одна настройка на пользователя),
`set_enabled()` (`SQLAlchemyWebSearchSettingRepository`) — upsert по
этому ключу.

Только схемная миграция, без сид-данных — таблица заполняется
исключительно через Telegram-команду `/websearch`. Отсутствие записи
для пользователя означает «выключено» (штатное значение по умолчанию,
не требует строки в этой таблице).

Revision ID: fa08c9adb7c6
Revises: c7f2f9a18fb0
Create Date: 2026-09-09 12:12:13.095004

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fa08c9adb7c6"
down_revision: str | Sequence[str] | None = "c7f2f9a18fb0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт таблицу user_web_search_settings."""
    op.create_table(
        "user_web_search_settings",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_web_search_settings_user_id_users"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    """Удаляет таблицу user_web_search_settings."""
    op.drop_table("user_web_search_settings")
