"""Команды индексации RAG Service — выпускаются только application/admin/ (docs/versions/05, §4)."""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.domain.rag.fragment import FragmentSourceType
from dekoder.shared.domain.identifiers import CaseId, DocumentId


@dataclass(frozen=True)
class IndexKnowledgeDocumentCommand:
    document_id: DocumentId


@dataclass(frozen=True)
class IndexKnowledgeCaseCommand:
    case_id: CaseId


@dataclass(frozen=True)
class RemoveFromIndexCommand:
    source_type: FragmentSourceType
    source_id: str
