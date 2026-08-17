"""Тесты `TxtParser` (Sprint 6, задача S6-05, §14.2/14.11)."""

from __future__ import annotations

import pytest

from dekoder.infrastructure.documents.parsers.txt_parser import TxtParser
from dekoder.shared.errors import ValidationError


class TestTxtParser:
    def test_parses_utf8_content_into_single_page(self) -> None:
        parser = TxtParser()

        pages = parser.parse("Привет, мир!".encode())

        assert len(pages) == 1
        assert pages[0].number is None
        assert pages[0].text == "Привет, мир!"

    def test_parses_windows_1251_content(self) -> None:
        parser = TxtParser()

        pages = parser.parse("Привет, мир!".encode("windows-1251"))

        assert pages[0].text == "Привет, мир!"

    def test_empty_content_raises_validation_error(self) -> None:
        parser = TxtParser()

        with pytest.raises(ValidationError) as exc_info:
            parser.parse(b"   \n\n  ")

        assert exc_info.value.code == "KNOWLEDGE_DOCUMENT_UNSUPPORTED"
