"""
ORM-модель таблицы `knowledge_documents` (Infrastructure Layer, Sprint 6,
задача S6-04, ADR-6.1/6.2, §14.5 «Плана реализации.md»).

Соответствует доменной сущности `dekoder.domain.knowledge.entities.
KnowledgeDocument`. Только метаданные документа — текст/векторы
фрагментов сюда не входят (ADR-6.2), единственный источник истины по ним
— Qdrant (payload точки, см. `infrastructure/qdrant/vector_repository.py`).

`document_type`/`status` — строки с `CheckConstraint`, тем же способом,
что и `MemoryRecordORM.category`/`.status` — доменные enum'ы
(`domain/knowledge/value_objects.py`) остаются чистым Python `Enum`.

`tags` — `sa.JSON`, тем же способом, что и `ProfileORM.forbidden_phrasing`
(список строк, не отдельная таблица — YAGNI для MVP).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from dekoder.infrastructure.persistence.base import Base


class KnowledgeDocumentORM(Base):
    """Строка таблицы `knowledge_documents`: метаданные и статус конвейера индексации одного документа."""

    __tablename__ = "knowledge_documents"

    id: Mapped[UUID] = mapped_column(sa.Uuid(), primary_key=True)
    title: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    document_type: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    source_filename: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    checksum: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    tags: Mapped[list[str]] = mapped_column(sa.JSON, nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    indexed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        sa.CheckConstraint(
            "document_type IN ('txt', 'markdown', 'docx', 'pdf')",
            name="ck_knowledge_documents_document_type",
        ),
        sa.CheckConstraint(
            "status IN ('uploaded', 'indexing', 'indexed', 'failed', 'unsupported')",
            name="ck_knowledge_documents_status",
        ),
        # Дедупликация по checksum (ADR-6.9) — `get_by_checksum` ищет по
        # этой колонке на каждой загрузке, уникальный индекс не даёт двум
        # конкурентным загрузкам одного и того же файла создать дубль.
        sa.Index("ix_knowledge_documents_checksum", "checksum", unique=True),
    )
