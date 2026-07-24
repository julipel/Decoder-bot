"""Документ базы знаний (docs/01, §4.6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from dekoder.shared.domain.identifiers import DocumentId


class DocumentIndexStatus(str, Enum):
    """Статус индексации документа (docs/02, §9)."""

    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"


@dataclass
class Document:
    """Метаданные документа. Файл содержимого хранится отдельно (см. FileStoragePort)."""

    document_id: DocumentId
    title: str
    category: str | None
    tags: tuple[str, ...] = field(default_factory=tuple)
    index_status: DocumentIndexStatus = DocumentIndexStatus.PENDING
