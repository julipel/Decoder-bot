"""Запросы и View DTO Knowledge Base (docs/versions/05, §5-6) — только чтение для панели администратора."""

from __future__ import annotations

from dataclasses import dataclass, field

from dekoder.domain.knowledge_base.case import CaseStatus
from dekoder.domain.knowledge_base.document import DocumentIndexStatus
from dekoder.shared.domain.identifiers import CaseId, DocumentId


@dataclass(frozen=True)
class GetKnowledgeDocumentsQuery:
    pass


@dataclass(frozen=True)
class GetKnowledgeCasesQuery:
    pass


@dataclass(frozen=True)
class KnowledgeDocumentView:
    document_id: DocumentId
    title: str
    category: str | None
    tags: tuple[str, ...] = field(default_factory=tuple)
    index_status: DocumentIndexStatus = DocumentIndexStatus.UPLOADED


@dataclass(frozen=True)
class KnowledgeCaseView:
    case_id: CaseId
    title: str
    task_type: str
    status: CaseStatus
