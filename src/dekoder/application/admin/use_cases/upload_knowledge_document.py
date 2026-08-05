from __future__ import annotations

from dekoder.application.admin.commands import UploadKnowledgeDocumentCommand
from dekoder.application.knowledge_base.ports import FileStoragePort, KnowledgeRepository
from dekoder.application.knowledge_base.queries import KnowledgeDocumentView
from dekoder.application.rag.use_cases.index_knowledge_document import (
    IndexKnowledgeDocumentUseCase,
)


class UploadKnowledgeDocumentUseCase:
    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        file_storage: FileStoragePort,
        index_document: IndexKnowledgeDocumentUseCase,
    ) -> None:
        self._knowledge_repository = knowledge_repository
        self._file_storage = file_storage
        self._index_document = index_document

    def execute(self, command: UploadKnowledgeDocumentCommand) -> KnowledgeDocumentView:
        raise NotImplementedError
