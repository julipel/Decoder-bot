from __future__ import annotations

from dekoder.application.knowledge_base.ports import KnowledgeRepository
from dekoder.application.knowledge_base.queries import GetKnowledgeCasesQuery, KnowledgeCaseView


class GetKnowledgeCasesUseCase:
    def __init__(self, knowledge_repository: KnowledgeRepository) -> None:
        self._knowledge_repository = knowledge_repository

    def execute(self, query: GetKnowledgeCasesQuery) -> list[KnowledgeCaseView]:
        raise NotImplementedError
