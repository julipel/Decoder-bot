from __future__ import annotations

from dekoder.application.admin.commands import UpdateKnowledgeCaseCommand
from dekoder.application.knowledge_base.ports import KnowledgeRepository
from dekoder.application.knowledge_base.queries import KnowledgeCaseView
from dekoder.application.rag.use_cases.index_knowledge_case import IndexKnowledgeCaseUseCase


class UpdateKnowledgeCaseUseCase:
    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        index_case: IndexKnowledgeCaseUseCase,
    ) -> None:
        self._knowledge_repository = knowledge_repository
        self._index_case = index_case

    def execute(self, command: UpdateKnowledgeCaseCommand) -> KnowledgeCaseView:
        raise NotImplementedError
