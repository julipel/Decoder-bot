"""
Оркестрация документов: сохранить в Knowledge Base → запустить индексацию
→ зафиксировать аудит (docs/02, §6 и §9). Admin — «верхний» потребитель
портов knowledge_base и search; сами эти модули друг о друге не знают.
"""

from __future__ import annotations

from dekoder.shared.domain.identifiers import DocumentId
from dekoder.modules.knowledge_base.application.ports import DocumentRepositoryPort, FileStoragePort
from dekoder.modules.knowledge_base.domain.document import Document
from dekoder.modules.logging_audit.application.ports import AuditPort
from dekoder.modules.search.application.ports import IndexingPort


class UploadDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        file_storage: FileStoragePort,
        indexing: IndexingPort,
        audit: AuditPort,
    ) -> None:
        self._document_repository = document_repository
        self._file_storage = file_storage
        self._indexing = indexing
        self._audit = audit

    def execute(self, document: Document, content: bytes) -> None:
        raise NotImplementedError


class UpdateDocumentUseCase:
    def __init__(self, document_repository: DocumentRepositoryPort, indexing: IndexingPort, audit: AuditPort) -> None:
        self._document_repository = document_repository
        self._indexing = indexing
        self._audit = audit

    def execute(self, document: Document) -> None:
        raise NotImplementedError


class RemoveDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        file_storage: FileStoragePort,
        indexing: IndexingPort,
        audit: AuditPort,
    ) -> None:
        self._document_repository = document_repository
        self._file_storage = file_storage
        self._indexing = indexing
        self._audit = audit

    def execute(self, document_id: DocumentId) -> None:
        raise NotImplementedError
