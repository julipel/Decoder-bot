"""Запрос и View DTO RAG Service (docs/versions/05, §5-6)."""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.domain.rag.fragment import FragmentSourceType
from dekoder.shared.domain.identifiers import CaseId, DocumentId, FragmentId


@dataclass(frozen=True)
class SearchKnowledgeQuery:
    query_text: str
    top_k: int


@dataclass(frozen=True)
class KnowledgeFragmentView:
    fragment_id: FragmentId
    source_type: FragmentSourceType
    source_id: DocumentId | CaseId
    text: str
    score: float | None
