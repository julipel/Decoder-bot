"""
Доменная сущность `KnowledgeDocument` (Sprint 6, задача S6-03, ADR-6.1) —
метаданные документа базы знаний, реализующая Этап 8 «Плана реализации.md».

Один плоский `frozen`-датакласс, стиль `domain/memory/entities.py::
MemoryRecord`: `id: UUID` без обёртки, ноль зависимостей от SQLAlchemy/
Qdrant/FastAPI. Текст и векторы фрагментов документа сюда не входят —
они не персистятся в SQL вообще (ADR-6.2), единственный источник истины
по ним — Qdrant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from dekoder.domain.knowledge.value_objects import DocumentStatus, DocumentType


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """Запись метаданных документа — заголовок, статус конвейера индексации, теги; фрагменты и векторы — в Qdrant."""

    id: UUID
    title: str
    document_type: DocumentType
    source_filename: str
    checksum: str
    status: DocumentStatus
    tags: tuple[str, ...]
    description: str | None
    chunk_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    indexed_at: datetime | None = field(default=None)

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title не может быть пустым")
        if not self.checksum.strip():
            raise ValueError("checksum не может быть пустым")
        if self.chunk_count < 0:
            raise ValueError("chunk_count не может быть отрицательным")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at не может быть раньше created_at")
