"""Тесты `StructuralChunker` (Sprint 6, задача S6-05, §14.4 шаг 7/14.11)."""

from __future__ import annotations

from dekoder.application.knowledge.pipeline import ParsedPage
from dekoder.infrastructure.documents.chunking.structural_chunker import StructuralChunker


class TestStructuralChunker:
    def test_single_small_page_becomes_one_chunk(self) -> None:
        chunker = StructuralChunker(chunk_size=1000, chunk_overlap=100)

        chunks = chunker.chunk([ParsedPage(number=None, text="Абзац один.\n\nАбзац два.")])

        assert len(chunks) == 1
        assert chunks[0].text == "Абзац один.\n\nАбзац два."
        assert chunks[0].page_number is None
        assert chunks[0].section_title is None

    def test_heading_sets_section_title_for_following_paragraphs(self) -> None:
        chunker = StructuralChunker(chunk_size=1000, chunk_overlap=0)

        chunks = chunker.chunk([ParsedPage(number=None, text="# Раздел A\n\nТекст A.\n\n## Раздел B\n\nТекст B.")])

        assert len(chunks) == 1
        assert "Раздел A" not in chunks[0].text  # заголовок не входит в текст фрагмента
        assert "Текст A." in chunks[0].text
        assert "Текст B." in chunks[0].text
        # Последний увиденный заголовок (Раздел B) — секция для всего оставшегося буфера.
        assert chunks[0].section_title == "Раздел B"

    def test_exceeding_chunk_size_starts_new_chunk(self) -> None:
        chunker = StructuralChunker(chunk_size=20, chunk_overlap=0)
        paragraphs = "Первый абзац текста.\n\nВторой абзац текста.\n\nТретий абзац текста."

        chunks = chunker.chunk([ParsedPage(number=None, text=paragraphs)])

        assert len(chunks) > 1
        assert all(len(chunk.text) <= 20 or "\n\n" not in chunk.text for chunk in chunks)

    def test_overlap_carries_tail_of_previous_chunk_into_next(self) -> None:
        chunker = StructuralChunker(chunk_size=25, chunk_overlap=10)
        paragraphs = "Абзац номер один тут.\n\nАбзац номер два тут."

        chunks = chunker.chunk([ParsedPage(number=None, text=paragraphs)])

        assert len(chunks) >= 2
        tail_of_first = chunks[0].text[-10:]
        assert tail_of_first in chunks[1].text

    def test_oversized_single_paragraph_is_hard_split(self) -> None:
        chunker = StructuralChunker(chunk_size=10, chunk_overlap=0)
        long_paragraph = "a" * 35

        chunks = chunker.chunk([ParsedPage(number=None, text=long_paragraph)])

        assert sum(len(chunk.text) for chunk in chunks) == 35
        assert all(len(chunk.text) <= 10 for chunk in chunks)

    def test_page_number_is_preserved_per_chunk(self) -> None:
        chunker = StructuralChunker(chunk_size=1000, chunk_overlap=0)

        chunks = chunker.chunk(
            [
                ParsedPage(number=1, text="Текст первой страницы."),
                ParsedPage(number=2, text="Текст второй страницы."),
            ]
        )

        assert [chunk.page_number for chunk in chunks] == [1, 2]

    def test_blank_page_produces_no_chunks(self) -> None:
        chunker = StructuralChunker(chunk_size=1000, chunk_overlap=0)

        chunks = chunker.chunk([ParsedPage(number=None, text="   \n\n  ")])

        assert chunks == []
