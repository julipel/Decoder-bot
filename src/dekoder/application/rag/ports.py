"""
VectorRepository (docs/versions/05, §7) — принимает исходный текст, не
вектор: вычисление эмбеддинга — деталь infrastructure/vector_storage/,
отдельного EmbeddingPort в v2 нет (05, §8, явный отказ от EmbeddingGateway).
"""

from __future__ import annotations

from typing import Protocol

from dekoder.domain.rag.fragment import FragmentSourceType, KnowledgeFragment


class VectorRepository(Protocol):
    def upsert_source(self, fragments: list[KnowledgeFragment]) -> None: ...

    def search(self, query_text: str, top_k: int) -> list[KnowledgeFragment]: ...

    def delete_by_source(self, source_type: FragmentSourceType, source_id: str) -> None: ...
