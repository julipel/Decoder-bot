from __future__ import annotations

from dekoder.application.admin.commands import CreateKnowledgeCaseCommand
from dekoder.application.knowledge_base.ports import KnowledgeRepository
from dekoder.application.knowledge_base.queries import KnowledgeCaseView
from dekoder.application.logging.ports import Logger
from dekoder.application.rag.use_cases.index_knowledge_case import IndexKnowledgeCaseUseCase


class CreateKnowledgeCaseUseCase:
    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        index_case: IndexKnowledgeCaseUseCase,
        logger: Logger,
    ) -> None:
        self._knowledge_repository = knowledge_repository
        self._index_case = index_case
        self._logger = logger

    def execute(self, command: CreateKnowledgeCaseCommand) -> KnowledgeCaseView:
        raise NotImplementedError
