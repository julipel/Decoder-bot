"""SQLite-реализация DocumentRepositoryPort."""

from __future__ import annotations

from dekoder.infrastructure.sqlite.connection import SqliteConnectionFactory
from dekoder.modules.knowledge_base.application.ports import DocumentRepositoryPort
from dekoder.modules.knowledge_base.domain.document import Document
from dekoder.shared.domain.identifiers import DocumentId


class SqliteDocumentRepository(DocumentRepositoryPort):
    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def add(self, document: Document) -> None:
        raise NotImplementedError

    def update(self, document: Document) -> None:
        raise NotImplementedError

    def delete(self, document_id: DocumentId) -> None:
        raise NotImplementedError

    def get(self, document_id: DocumentId) -> Document | None:
        raise NotImplementedError

    def list_all(self) -> list[Document]:
        raise NotImplementedError
