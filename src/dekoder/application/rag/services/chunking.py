"""Разбиение текста документа/кейса на фрагменты — алгоритм, не доменная сущность (docs/versions/03, §4)."""

from __future__ import annotations


class DocumentChunker:
    def __init__(self, max_chunk_size: int) -> None:
        self._max_chunk_size = max_chunk_size

    def split(self, text: str) -> list[str]:
        raise NotImplementedError
