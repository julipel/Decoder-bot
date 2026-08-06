"""
`StructuralChunker` — реализация `TextChunker` (§14.4, шаг 7 «Разбиение
по смысловым и структурным границам», задача S6-05).

Единицы разбиения — абзацы (текст между пустыми строками), не отдельные
предложения/символы: это и есть «структурная граница» источника, общая
для TXT/Markdown/DOCX (после нормализации заголовков в `DocxParser`)/PDF.
Абзацы жадно упаковываются во фрагмент до `chunk_size` символов
(эвристика символов, не токены модели — тот же приём, что и
`PromptSettings.token_budget`, ADR-4.4); переполнение начинает новый
фрагмент с «хвостом» предыдущего в `chunk_overlap` символов — контекст на
границе не теряется полностью, но и не задваивается на весь размер
фрагмента.

Заголовки Markdown-разметки (`#`..`######`) не попадают в текст фрагмента
— они становятся `section_title` для всех абзацев вплоть до следующего
заголовка (§14.5 «заголовок раздела»). TXT/PDF без такой разметки просто
не производят заголовков — `section_title=None`, что и означает «если
доступен» из §14.5.
"""

from __future__ import annotations

import re

from dekoder.application.knowledge.pipeline import ChunkDraft, ParsedPage

_PARAGRAPH_BOUNDARY = re.compile(r"\n\s*\n+")
_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+)$")


def _split_paragraphs(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in _PARAGRAPH_BOUNDARY.split(text) if paragraph.strip()]


def _heading_text(paragraph: str) -> str | None:
    """Заголовок — абзац из одной строки вида `# Текст`; абзац из нескольких строк заголовком не считается."""
    if "\n" in paragraph:
        return None
    match = _HEADING_PATTERN.match(paragraph)
    return match.group(1).strip() if match else None


def _split_oversized(text: str, chunk_size: int) -> list[str]:
    """Абзац длиннее `chunk_size` (страница без пустых строк) режется без перекрытия — только чтобы удержать бюджет."""
    if len(text) <= chunk_size:
        return [text]
    return [text[start : start + chunk_size] for start in range(0, len(text), chunk_size)]


class StructuralChunker:
    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def chunk(self, pages: list[ParsedPage]) -> list[ChunkDraft]:
        drafts: list[ChunkDraft] = []
        for page in pages:
            drafts.extend(self._chunk_page(page))
        return drafts

    def _chunk_page(self, page: ParsedPage) -> list[ChunkDraft]:
        drafts: list[ChunkDraft] = []
        section_title: str | None = None
        buffer = ""

        for paragraph in _split_paragraphs(page.text):
            heading = _heading_text(paragraph)
            if heading is not None:
                section_title = heading
                continue

            for piece in _split_oversized(paragraph, self._chunk_size):
                candidate = f"{buffer}\n\n{piece}" if buffer else piece
                if len(candidate) <= self._chunk_size:
                    buffer = candidate
                    continue

                drafts.append(ChunkDraft(text=buffer, page_number=page.number, section_title=section_title))
                overlap_tail = buffer[-self._chunk_overlap :] if self._chunk_overlap > 0 else ""
                buffer = f"{overlap_tail}\n\n{piece}" if overlap_tail else piece

        if buffer.strip():
            drafts.append(ChunkDraft(text=buffer, page_number=page.number, section_title=section_title))
        return drafts
