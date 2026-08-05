from __future__ import annotations

from dekoder.application.admin.commands import UpdateKnowledgeDocumentCommand
from dekoder.application.knowledge_base.ports import KnowledgeRepository
from dekoder.application.knowledge_base.queries import KnowledgeDocumentView
from dekoder.application.rag.use_cases.index_knowledge_document import (
    IndexKnowledgeDocumentUseCase,
)


class UpdateKnowledgeDocumentUseCase:
    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        index_document: IndexKnowledgeDocumentUseCase,
    ) -> None:
        self._knowledge_repository = knowledge_repository
        self._index_document = index_document

    def execute(self, command: UpdateKnowledgeDocumentCommand) -> KnowledgeDocumentView:
        raise NotImplementedError
