from __future__ import annotations

from dekoder.application.admin.commands import LinkDocumentToCaseCommand
from dekoder.application.knowledge_base.ports import KnowledgeRepository


class LinkDocumentToCaseUseCase:
    def __init__(self, knowledge_repository: KnowledgeRepository) -> None:
        self._knowledge_repository = knowledge_repository

    def execute(self, command: LinkDocumentToCaseCommand) -> None:
        raise NotImplementedError
