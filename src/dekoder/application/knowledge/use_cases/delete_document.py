"""
`DeleteKnowledgeDocumentUseCase` — удаление документа целиком (Sprint 6,
задача S6-06, §14.12: «удаление документа удаляет и его векторы»).

Порядок шагов важен: векторы (Qdrant) → файл (`DocumentStorage`) → запись
метаданных (`KnowledgeDocumentRepository`) — запись БД удаляется
последней, поэтому если удаление прервётся на середине (сбой Qdrant/
файловой системы), документ остаётся видимым и попытку можно повторить,
а не исчезает из списков, оставляя осиротевшие векторы/файл.
"""

from __future__ import annotations

from uuid import UUID

from dekoder.application.knowledge.ports import DocumentStorage, KnowledgeDocumentRepository, VectorRepository
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


class DeleteKnowledgeDocumentUseCase:
    def __init__(
        self,
        document_repository: KnowledgeDocumentRepository,
        document_storage: DocumentStorage,
        vector_repository: VectorRepository,
    ) -> None:
        self._document_repository = document_repository
        self._document_storage = document_storage
        self._vector_repository = vector_repository

    async def execute(self, document_id: UUID) -> None:
        await self._vector_repository.delete_by_document(document_id)
        await self._document_storage.delete(document_id)
        await self._document_repository.delete(document_id)
        _logger.info("knowledge_document_deleted", document_id=str(document_id))
