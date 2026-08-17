"""Тесты `SearchResult`/`SourceReference` (domain/knowledge/search.py, задача S6-03)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from dekoder.domain.knowledge.search import SearchResult, SourceReference


def _make_source(**overrides: object) -> SourceReference:
    defaults: dict[str, object] = {
        "document_id": uuid4(),
        "document_title": "Условия гарантии",
        "chunk_index": 0,
        "section_title": None,
        "page_number": None,
    }
    defaults.update(overrides)
    return SourceReference(**defaults)  # type: ignore[arg-type]


class TestSearchResultCreation:
    def test_creates_valid_result(self) -> None:
        result = SearchResult(text="Гарантия действует 24 месяца.", score=0.87, source=_make_source())

        assert result.text == "Гарантия действует 24 месяца."
        assert result.score == 0.87

    def test_accepts_source_with_page_and_section(self) -> None:
        source = _make_source(section_title="Условия", page_number=3)

        result = SearchResult(text="Текст.", score=0.5, source=source)

        assert result.source.section_title == "Условия"
        assert result.source.page_number == 3


class TestSearchResultInvariants:
    def test_empty_text_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="text"):
            SearchResult(text="", score=0.5, source=_make_source())

    def test_blank_text_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="text"):
            SearchResult(text="   ", score=0.5, source=_make_source())
