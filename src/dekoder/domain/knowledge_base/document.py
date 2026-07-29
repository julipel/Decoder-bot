"""KnowledgeDocument — метаданные документа заказчика; физически удаляется, не архивируется (docs/versions/04, §4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from dekoder.shared.domain.identifiers import DocumentId


class DocumentIndexStatus(str, Enum):
    UPLOADED = "uploaded"
    INDEXED = "indexed"
    INDEXING_FAILED = "indexing_failed"
    DELETED = "deleted"


@dataclass
class KnowledgeDocument:
    document_id: DocumentId
    title: str
    category: str | None
    tags: tuple[str, ...] = field(default_factory=tuple)
    index_status: DocumentIndexStatus = DocumentIndexStatus.UPLOADED
