"""Тесты `MarkdownParser` (Sprint 6, задача S6-05, §14.2/14.11)."""

from __future__ import annotations

import pytest

from dekoder.infrastructure.documents.parsers.markdown_parser import MarkdownParser
from dekoder.shared.errors import ValidationError


class TestMarkdownParser:
    def test_parses_content_preserving_heading_markup(self) -> None:
        parser = MarkdownParser()

        pages = parser.parse("# Заголовок\n\nТекст абзаца.".encode())

        assert len(pages) == 1
        assert pages[0].number is None
        assert pages[0].text == "# Заголовок\n\nТекст абзаца."

    def test_empty_content_raises_validation_error(self) -> None:
        parser = MarkdownParser()

        with pytest.raises(ValidationError) as exc_info:
            parser.parse(b"")

        assert exc_info.value.code == "KNOWLEDGE_DOCUMENT_UNSUPPORTED"
