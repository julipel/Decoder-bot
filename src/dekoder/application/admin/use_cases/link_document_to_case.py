from __future__ import annotations

from dekoder.application.admin.commands import LinkDocumentToCaseCommand
from dekoder.application.knowledge_base.ports import KnowledgeRepository
from dekoder.application.logging.ports import Logger


class LinkDocumentToCaseUseCase:
    def __init__(self, knowledge_repository: KnowledgeRepository, logger: Logger) -> None:
        self._knowledge_repository = knowledge_repository
        self._logger = logger

    def execute(self, command: LinkDocumentToCaseCommand) -> None:
        raise NotImplementedError
