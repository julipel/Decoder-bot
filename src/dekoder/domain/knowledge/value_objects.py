"""
Enum'ы доменной модели базы знаний (Sprint 6, задача S6-03, ADR-6.1/6.7)
— Этап 8 «Плана реализации.md» (§14.2/14.4).

`Enum`, не `str, Enum` — по стилю `domain/memory/value_objects.py`/
`domain/profile/value_objects.py`.
"""

from __future__ import annotations

from enum import Enum


class DocumentType(Enum):
    """Поддерживаемые форматы MVP (§14.2). OCR и документы-только-из-картинок не входят в Sprint 6 (ADR-6.7)."""

    TXT = "txt"
    MARKDOWN = "markdown"
    DOCX = "docx"
    PDF = "pdf"


class DocumentStatus(Enum):
    """
    Единый статус документа, объединяющий и его жизненный цикл, и
    состояние конвейера индексации (§14.3 «Плана реализации.md» называет
    их отдельно как `DocumentStatus`/`IndexingStatus` — в Sprint 6 это
    один enum, ADR-6.1: заведение второго измерения статуса не оправдано
    для MVP, где документ либо ещё не обработан, либо обработан, либо
    обработка не удалась).

    `UNSUPPORTED` — не ошибка обработки, а корректный конечный статус
    (§14.2): документ без текстового слоя (например, PDF из одних
    картинок) распознан и отклонён предсказуемо, не уронив конвейер.
    """

    UPLOADED = "uploaded"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"
