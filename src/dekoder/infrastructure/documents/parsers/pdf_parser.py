"""
`PdfParser` — реализация `DocumentParser` для формата PDF с текстовым
слоем (§14.2, задача S6-05). OCR не входит в MVP — PDF из одних картинок
(без текстового слоя) — не ошибка обработки, а `ValidationError`, которую
вызывающий use case превращает в `DocumentStatus.UNSUPPORTED`.
"""

from __future__ import annotations

import io

from pypdf import PdfReader

from dekoder.application.knowledge.pipeline import ParsedPage
from dekoder.shared.errors import ValidationError


class PdfParser:
    """Единственный из четырёх парсеров, возвращающий несколько `ParsedPage` — по одной на страницу (§14.5)."""

    def parse(self, content: bytes) -> list[ParsedPage]:
        try:
            reader = PdfReader(io.BytesIO(content))
        except Exception as exc:
            raise ValidationError(
                message=f"Не удалось разобрать PDF-документ: {exc}",
                user_message="Файл повреждён или не является корректным PDF-документом.",
                code="KNOWLEDGE_DOCUMENT_UNSUPPORTED",
                cause=exc,
            ) from exc

        pages: list[ParsedPage] = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(ParsedPage(number=index, text=text))

        if not pages:
            raise ValidationError(
                message="PDF-документ не содержит текстового слоя",
                user_message="Документ не содержит распознаваемого текста (вероятно, это скан) — "
                "распознавание изображений (OCR) не входит в MVP.",
                code="KNOWLEDGE_DOCUMENT_UNSUPPORTED",
            )
        return pages
