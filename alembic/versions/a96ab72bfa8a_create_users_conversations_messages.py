"""create users conversations messages

Первая миграция схемы Sprint 2 (задача S2-02): таблицы `users`,
`conversations`, `messages` вместе с внешними ключами, ограничениями и
индексами, описанными в backlog_2.md §7.

Сгенерирована `alembic revision --autogenerate` и вручную выверена и
дополнена комментариями: autogenerate верно распознал CHECK-ограничения
(`ck_messages_role`, `ck_messages_content_not_empty`) и частичный
уникальный индекс (`uq_conversations_active_user`, `sqlite_where`), но
порядок операций переставлен вручную под явное требование задачи —
`upgrade`: users → conversations → messages → индексы; `downgrade` —
строго в обратном порядке (сначала индексы, включая частичный, затем
таблицы messages → conversations → users).

Revision ID: a96ab72bfa8a
Revises:
Create Date: 2026-07-31 23:22:53.377124

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a96ab72bfa8a"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт таблицы users → conversations → messages, затем индексы."""
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_user_id", name="uq_users_telegram_user_id"),
    )
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_conversations_user_id_users"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
        sa.CheckConstraint(
            "length(trim(content, ' ' || char(9) || char(10) || char(13))) > 0",
            name="ck_messages_content_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], name="fk_messages_conversation_id_conversations"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_conversations_user_id", "conversations", ["user_id"], unique=False)
    # Частичный уникальный индекс — единственная защита инварианта «не более
    # одного активного диалога на пользователя» на уровне БД: обычный
    # UNIQUE(user_id, closed_at) недостаточен, т. к. SQL допускает несколько
    # строк с NULL в уникальном составном индексе.
    op.create_index(
        "uq_conversations_active_user",
        "conversations",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("closed_at IS NULL"),
    )
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"], unique=False)


def downgrade() -> None:
    """Удаляет индексы (включая частичный), затем таблицы messages → conversations → users."""
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_index("uq_conversations_active_user", table_name="conversations", sqlite_where=sa.text("closed_at IS NULL"))
    op.drop_index("ix_conversations_user_id", table_name="conversations")

    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("users")
