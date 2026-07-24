"""
Реализация IndexingPort: читает документ/кейс из Knowledge Base, разбивает
на фрагменты, получает векторы и сохраняет их в векторном хранилище
(docs/02, §9). Единственное место, где search-модуль читает knowledge_base
(только чтение метаданных и содержимого — docs/02, §6).
"""

from __future__ import annotations

from dekoder.shared.domain.identifiers import CaseId, DocumentId
from dekoder.modules.knowledge_base.application.ports import (
    CaseRepositoryPort,
    DocumentRepositoryPort,
    FileStoragePort,
)
from dekoder.modules.search.application.ports import EmbeddingPort, IndexingPort, VectorStorePort
from dekoder.modules.search.application.services.chunking import DocumentChunker
from dekoder.modules.search.domain.fragment import FragmentSourceType


class IndexDocumentUseCase(IndexingPort):
    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        case_repository: CaseRepositoryPort,
        file_storage: FileStoragePort,
        chunker: DocumentChunker,
        embedding: EmbeddingPort,
        vector_store: VectorStorePort,
    ) -> None:
        self._document_repository = document_repository
        self._case_repository = case_repository
        self._file_storage = file_storage
        self._chunker = chunker
        self._embedding = embedding
        self._vector_store = vector_store

    def index_document(self, document_id: DocumentId) -> None:
        raise NotImplementedError

    def index_case(self, case_id: CaseId) -> None:
        raise NotImplementedError

    def remove_from_index(self, source_type: FragmentSourceType, source_id: str) -> None:
        raise NotImplementedError
