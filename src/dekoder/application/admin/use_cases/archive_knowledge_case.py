from __future__ import annotations

from dekoder.application.admin.commands import ArchiveKnowledgeCaseCommand
from dekoder.application.knowledge_base.ports import KnowledgeRepository
from dekoder.application.logging.ports import Logger
from dekoder.application.rag.use_cases.remove_from_index import RemoveFromIndexUseCase


class ArchiveKnowledgeCaseUseCase:
    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        remove_from_index: RemoveFromIndexUseCase,
        logger: Logger,
    ) -> None:
        self._knowledge_repository = knowledge_repository
        self._remove_from_index = remove_from_index
        self._logger = logger

    def execute(self, command: ArchiveKnowledgeCaseCommand) -> None:
        raise NotImplementedError
