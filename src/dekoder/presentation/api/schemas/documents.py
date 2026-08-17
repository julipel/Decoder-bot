"""
`DocumentResponse` — pydantic-схема ответа admin REST для документов
базы знаний (Sprint 8, задача S8-05, ADR-8.6).

Поля 1:1 с `domain.knowledge.entities.KnowledgeDocument`, кроме
`checksum` — внутренняя деталь дедупликации (ADR-6.9), не нужна
администратору и умышленно не входит в ответ.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dekoder.domain.knowledge.value_objects import DocumentStatus, DocumentType


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    document_type: DocumentType
    source_filename: str
    status: DocumentStatus
    tags: tuple[str, ...]
    description: str | None
    chunk_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    indexed_at: datetime | None
