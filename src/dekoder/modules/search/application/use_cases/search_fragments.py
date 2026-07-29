"""Реализация KnowledgeSearchPort: превращает запрос в вектор и ищет ближайшие фрагменты."""

from __future__ import annotations

from dekoder.modules.search.application.ports import (
    EmbeddingPort,
    KnowledgeSearchPort,
    VectorStorePort,
)
from dekoder.modules.search.domain.fragment import Fragment


class SearchFragmentsUseCase(KnowledgeSearchPort):
    def __init__(self, embedding: EmbeddingPort, vector_store: VectorStorePort) -> None:
        self._embedding = embedding
        self._vector_store = vector_store

    def search(self, query: str, top_k: int) -> list[Fragment]:
        raise NotImplementedError
