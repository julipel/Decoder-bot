"""
`SourceReference`/`SearchResult` (Sprint 6, задача S6-03, §14.3/14.7
«Плана реализации.md») — результат семантического поиска по базе знаний.

Не персистятся — собираются `KnowledgeSearchService`
(`application/knowledge/services/semantic_search_service.py`, задача
S6-07) из ответа Qdrant на каждый запрос, тем же приёмом, что домен не
хранит `LLMResponse`/`PromptBuildResult`.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Источник фрагмента — то, что §14.8 требует уметь показать/сохранить рядом с использованным ответом."""

    document_id: UUID
    document_title: str
    chunk_index: int
    section_title: str | None
    page_number: int | None


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Один найденный фрагмент с оценкой релевантности и источником (§14.7: «возврат источников»)."""

    text: str
    score: float
    source: SourceReference

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("text не может быть пустым")
