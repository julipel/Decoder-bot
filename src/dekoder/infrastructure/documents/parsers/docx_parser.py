"""`DocxParser` — реализация `DocumentParser` для формата DOCX (§14.2, задача S6-05)."""

from __future__ import annotations

import io
import re

import docx

from dekoder.application.knowledge.pipeline import ParsedPage
from dekoder.shared.errors import ValidationError

_HEADING_STYLE_PATTERN = re.compile(r"^Heading (\d+)$")


def _heading_level(style_name: str) -> int | None:
    """`None` — не заголовок; иначе уровень 1-6 (Title/Subtitle — 1, `Heading N` — N, ограниченный 6)."""
    if style_name in ("Title", "Subtitle"):
        return 1
    match = _HEADING_STYLE_PATTERN.match(style_name)
    if match:
        return min(int(match.group(1)), 6)
    return None


class DocxParser:
    """
    Заголовки (стили `Title`/`Heading N`) переводятся в markdown-разметку
    (`#`..`######`) прямо в тексте — единственный способ передать
    структуру документа дальше по конвейеру без отдельного канала
    метаданных: `StructuralChunker` распознаёт заголники по этой же
    разметке для Markdown, повторное распознавание не требуется.
    """

    def parse(self, content: bytes) -> list[ParsedPage]:
        try:
            document = docx.Document(io.BytesIO(content))
        except Exception as exc:
            # python-docx/zipfile поднимают разные типы исключений на
            # разных стадиях повреждения архива (BadZipFile, KeyError,
            # PackageNotFoundError, ошибки разбора внутреннего XML) — все
            # они означают одно и то же с точки зрения конвейера: файл не
            # является корректным DOCX (§14.2).
            raise ValidationError(
                message=f"Не удалось разобрать DOCX-документ: {exc}",
                user_message="Файл повреждён или не является корректным DOCX-документом.",
                code="KNOWLEDGE_DOCUMENT_UNSUPPORTED",
                cause=exc,
            ) from exc

        lines: list[str] = []
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            style_name = paragraph.style.name if paragraph.style is not None else ""
            level = _heading_level(style_name)
            lines.append(f"{'#' * level} {text}" if level is not None else text)

        full_text = "\n\n".join(lines)
        if not full_text.strip():
            raise ValidationError(
                message="DOCX-документ не содержит текста",
                user_message="Документ пуст — нечего индексировать.",
                code="KNOWLEDGE_DOCUMENT_UNSUPPORTED",
            )
        return [ParsedPage(number=None, text=full_text)]
