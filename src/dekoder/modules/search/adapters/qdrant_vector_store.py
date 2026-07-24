"""
Реализация VectorStorePort поверх Qdrant (docs/02: «изолирует всё
взаимодействие с Qdrant — остальные компоненты не обращаются к Qdrant
напрямую»). Клиент Qdrant не подключается на этом шаге (зависимости не
устанавливаются) — только структура адаптера.
"""

from __future__ import annotations

from dekoder.modules.search.application.ports import VectorStorePort
from dekoder.modules.search.domain.fragment import Fragment, FragmentSourceType


class QdrantVectorStore(VectorStorePort):
    def __init__(self, qdrant_url: str, collection_name: str) -> None:
        self._qdrant_url = qdrant_url
        self._collection_name = collection_name

    def upsert(self, fragments: list[Fragment], vectors: list[list[float]]) -> None:
        raise NotImplementedError

    def query(self, vector: list[float], top_k: int) -> list[Fragment]:
        raise NotImplementedError

    def delete_by_source(self, source_type: FragmentSourceType, source_id: str) -> None:
        raise NotImplementedError
