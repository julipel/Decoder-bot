from __future__ import annotations

from dekoder.application.knowledge_base.ports import FileStoragePort, KnowledgeRepository
from dekoder.application.rag.commands import IndexKnowledgeCaseCommand
from dekoder.application.rag.ports import VectorRepository
from dekoder.application.rag.services.chunking import DocumentChunker


class IndexKnowledgeCaseUseCase:
    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        file_storage: FileStoragePort,
        chunker: DocumentChunker,
        vector_repository: VectorRepository,
    ) -> None:
        self._knowledge_repository = knowledge_repository
        self._file_storage = file_storage
        self._chunker = chunker
        self._vector_repository = vector_repository

    def execute(self, command: IndexKnowledgeCaseCommand) -> None:
        raise NotImplementedError
