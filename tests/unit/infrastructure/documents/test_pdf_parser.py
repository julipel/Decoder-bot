"""Тесты `PdfParser` (Sprint 6, задача S6-05, §14.2/14.11) — OCR/сканы не входят в MVP."""

from __future__ import annotations

import io

import pytest
from pypdf import PdfWriter
from tests.support.pdf_builder import build_minimal_pdf

from dekoder.infrastructure.documents.parsers.pdf_parser import PdfParser
from dekoder.shared.errors import ValidationError


def _build_blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class TestPdfParser:
    def test_returns_one_page_per_original_page_with_text(self) -> None:
        # Латиница, не кириллица: минимальный hand-built PDF (без
        # встроенного шрифта с полноценной CID-кодировкой) поддерживает
        # только WinAnsi/Standard-кодировку базового шрифта Helvetica —
        # проверяется логика самого парсера (постраничность/непустой
        # текст), не поддержка конкретного алфавита.
        parser = PdfParser()

        pages = parser.parse(build_minimal_pdf(["First page text", "Second page text"]))

        assert [page.number for page in pages] == [1, 2]
        assert pages[0].text == "First page text"
        assert pages[1].text == "Second page text"

    def test_pdf_without_text_layer_raises_validation_error(self) -> None:
        parser = PdfParser()

        with pytest.raises(ValidationError) as exc_info:
            parser.parse(_build_blank_pdf())

        assert exc_info.value.code == "KNOWLEDGE_DOCUMENT_UNSUPPORTED"

    def test_corrupted_content_raises_validation_error(self) -> None:
        parser = PdfParser()

        with pytest.raises(ValidationError) as exc_info:
            parser.parse(b"not a pdf file")

        assert exc_info.value.code == "KNOWLEDGE_DOCUMENT_UNSUPPORTED"
