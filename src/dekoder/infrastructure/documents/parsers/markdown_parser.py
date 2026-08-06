"""
`MarkdownParser` — реализация `DocumentParser` для формата Markdown
(§14.2, задача S6-05).

Текст не преобразуется (заголовки `#`/`##` остаются как есть в исходном
тексте) — `StructuralChunker` (`infrastructure/documents/chunking/
structural_chunker.py`) сам распознаёт эту разметку при разбиении на
фрагменты, парсер её не интерпретирует.
"""

from __future__ import annotations

from dekoder.application.knowledge.pipeline import ParsedPage
from dekoder.infrastructure.documents.parsers.text_encoding import decode_text_bytes
from dekoder.shared.errors import ValidationError


class MarkdownParser:
    def parse(self, content: bytes) -> list[ParsedPage]:
        text = decode_text_bytes(content)
        if not text.strip():
            raise ValidationError(
                message="Markdown-документ не содержит текста",
                user_message="Документ пуст — нечего индексировать.",
                code="KNOWLEDGE_DOCUMENT_UNSUPPORTED",
            )
        return [ParsedPage(number=None, text=text)]
