from __future__ import annotations

from dekoder.application.admin.commands import RemoveKnowledgeDocumentCommand
from dekoder.application.knowledge_base.ports import FileStoragePort, KnowledgeRepository
from dekoder.application.rag.use_cases.remove_from_index import RemoveFromIndexUseCase


class RemoveKnowledgeDocumentUseCase:
    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        file_storage: FileStoragePort,
        remove_from_index: RemoveFromIndexUseCase,
    ) -> None:
        self._knowledge_repository = knowledge_repository
        self._file_storage = file_storage
        self._remove_from_index = remove_from_index

    def execute(self, command: RemoveKnowledgeDocumentCommand) -> None:
        raise NotImplementedError
