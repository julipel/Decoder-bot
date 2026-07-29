from __future__ import annotations

from dekoder.application.rag.ports import VectorRepository
from dekoder.application.rag.queries import KnowledgeFragmentView, SearchKnowledgeQuery


class SearchKnowledgeUseCase:
    def __init__(self, vector_repository: VectorRepository) -> None:
        self._vector_repository = vector_repository

    def execute(self, query: SearchKnowledgeQuery) -> list[KnowledgeFragmentView]:
        raise NotImplementedError
