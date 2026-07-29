from __future__ import annotations

from dekoder.application.knowledge_base.ports import KnowledgeRepository
from dekoder.application.knowledge_base.queries import (
    GetKnowledgeDocumentsQuery,
    KnowledgeDocumentView,
)


class GetKnowledgeDocumentsUseCase:
    def __init__(self, knowledge_repository: KnowledgeRepository) -> None:
        self._knowledge_repository = knowledge_repository

    def execute(self, query: GetKnowledgeDocumentsQuery) -> list[KnowledgeDocumentView]:
        raise NotImplementedError
