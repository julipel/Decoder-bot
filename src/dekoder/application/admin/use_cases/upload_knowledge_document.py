from __future__ import annotations

from dekoder.application.admin.commands import UploadKnowledgeDocumentCommand
from dekoder.application.knowledge_base.ports import FileStoragePort, KnowledgeRepository
from dekoder.application.knowledge_base.queries import KnowledgeDocumentView
from dekoder.application.logging.ports import Logger
from dekoder.application.rag.use_cases.index_knowledge_document import (
    IndexKnowledgeDocumentUseCase,
)


class UploadKnowledgeDocumentUseCase:
    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        file_storage: FileStoragePort,
        index_document: IndexKnowledgeDocumentUseCase,
        logger: Logger,
    ) -> None:
        self._knowledge_repository = knowledge_repository
        self._file_storage = file_storage
        self._index_document = index_document
        self._logger = logger

    def execute(self, command: UploadKnowledgeDocumentCommand) -> KnowledgeDocumentView:
        raise NotImplementedError
