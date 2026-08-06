"""Command/Result DTO конвейера индексации (Sprint 6, S6-06) — тот же приём, что `application/memory/dto.py`."""

from __future__ import annotations

from dataclasses import dataclass, field

from dekoder.domain.knowledge.entities import KnowledgeDocument


@dataclass(frozen=True)
class IndexDocumentCommand:
    title: str
    source_filename: str
    content: bytes
    tags: tuple[str, ...] = field(default_factory=tuple)
    description: str | None = None


@dataclass(frozen=True)
class IndexDocumentResult:
    document: KnowledgeDocument
