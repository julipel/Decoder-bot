"""create knowledge_documents

Схемная миграция базы знаний (Sprint 6, задача S6-04, ADR-6.1/6.2,
`backlog_6.md` §14.5): таблица `knowledge_documents` — только метаданные
документа, текст/векторы фрагментов не персистятся здесь (ADR-6.2,
единственный источник истины по ним — Qdrant). Уникальный индекс на
`checksum` — точка дедупликации (ADR-6.9).

Как и `memory_records` (Sprint 5) — только схемная миграция, без
сид-данных: `knowledge_documents` создаётся исключительно через
`scripts/index_document.py` (задача S6-09), не через bootstrap-сидер.

Revision ID: 82d9884e32a2
Revises: 161899ea36c0
Create Date: 2026-08-06 19:52:10.013931

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "82d9884e32a2"
down_revision: str | Sequence[str] | None = "161899ea36c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт таблицу knowledge_documents, затем уникальный индекс по checksum."""
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("document_type", sa.String(length=16), nullable=False),
        sa.Column("source_filename", sa.String(length=256), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "document_type IN ('txt', 'markdown', 'docx', 'pdf')",
            name="ck_knowledge_documents_document_type",
        ),
        sa.CheckConstraint(
            "status IN ('uploaded', 'indexing', 'indexed', 'failed', 'unsupported')",
            name="ck_knowledge_documents_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_knowledge_documents_checksum",
        "knowledge_documents",
        ["checksum"],
        unique=True,
    )


def downgrade() -> None:
    """Удаляет индекс по checksum, затем таблицу knowledge_documents."""
    op.drop_index("ix_knowledge_documents_checksum", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
