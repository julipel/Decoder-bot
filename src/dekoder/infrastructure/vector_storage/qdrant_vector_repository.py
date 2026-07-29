"""QdrantVectorRepository — реализация VectorRepository; эмбеддинг — внутренняя деталь (docs/versions/05, §8)."""

from __future__ import annotations

from dekoder.application.rag.ports import VectorRepository
from dekoder.domain.rag.fragment import FragmentSourceType, KnowledgeFragment


class QdrantVectorRepository(VectorRepository):
    def __init__(self, qdrant_url: str, collection_name: str) -> None:
        self._qdrant_url = qdrant_url
        self._collection_name = collection_name

    def upsert_source(self, fragments: list[KnowledgeFragment]) -> None:
        raise NotImplementedError

    def search(self, query_text: str, top_k: int) -> list[KnowledgeFragment]:
        raise NotImplementedError

    def delete_by_source(self, source_type: FragmentSourceType, source_id: str) -> None:
        raise NotImplementedError
