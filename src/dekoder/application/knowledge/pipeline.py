"""
Внутренние DTO конвейера индексации (Sprint 6, задача S6-05, §14.4 «Плана
реализации.md») — промежуточные результаты шагов «извлечение текста» →
«разбиение на фрагменты» → «эмбеддинги», между `DocumentParser`,
`TextChunker`, `EmbeddingProvider`, `VectorRepository` (`ports.py`).

Не доменные сущности — как `LLMRequest`/`LLMResponse`
(`application/conversation/dto.py`), они существуют только на время
одного вызова `IndexKnowledgeDocumentUseCase.execute()` и никогда не
персистятся напрямую.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedPage:
    """
    Одна «страница» извлечённого текста (§14.5 «номер страницы, если
    доступен»). `number` — `None` для форматов без естественного понятия
    страницы (TXT/Markdown/DOCX — один `ParsedPage` на весь документ);
    PDF-парсер возвращает по одному `ParsedPage` на страницу оригинала.
    """

    number: int | None
    text: str


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    """Один фрагмент после разбиения (`TextChunker.chunk`), ещё без эмбеддинга и без `document_id`/`chunk_index`."""

    text: str
    page_number: int | None
    section_title: str | None


@dataclass(frozen=True, slots=True)
class EmbeddedChunk:
    """Фрагмент с готовым вектором и присвоенным номером — то, что `VectorRepository.upsert_chunks` пишет в Qdrant."""

    chunk_index: int
    text: str
    page_number: int | None
    section_title: str | None
    vector: tuple[float, ...]
