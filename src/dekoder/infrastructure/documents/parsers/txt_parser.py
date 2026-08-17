"""`TxtParser` — реализация `DocumentParser` для формата TXT (§14.2, задача S6-05)."""

from __future__ import annotations

from dekoder.application.knowledge.pipeline import ParsedPage
from dekoder.infrastructure.documents.parsers.text_encoding import decode_text_bytes
from dekoder.shared.errors import ValidationError


class TxtParser:
    """Формат без понятия страниц/структуры — весь файл возвращается одним `ParsedPage` (`number=None`)."""

    def parse(self, content: bytes) -> list[ParsedPage]:
        text = decode_text_bytes(content)
        if not text.strip():
            raise ValidationError(
                message="TXT-документ не содержит текста",
                user_message="Документ пуст — нечего индексировать.",
                code="KNOWLEDGE_DOCUMENT_UNSUPPORTED",
            )
        return [ParsedPage(number=None, text=text)]
