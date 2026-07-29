from __future__ import annotations

from dekoder.application.knowledge_base.ports import KnowledgeRepository
from dekoder.domain.knowledge_base.case import KnowledgeCase
from dekoder.domain.knowledge_base.document import KnowledgeDocument
from dekoder.infrastructure.persistence.sqlite_connection import SqliteConnectionFactory
from dekoder.shared.domain.identifiers import CaseId, DocumentId


class SqliteKnowledgeRepository(KnowledgeRepository):
    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def add_document(self, document: KnowledgeDocument) -> None:
        raise NotImplementedError

    def update_document(self, document: KnowledgeDocument) -> None:
        raise NotImplementedError

    def delete_document(self, document_id: DocumentId) -> None:
        raise NotImplementedError

    def get_document(self, document_id: DocumentId) -> KnowledgeDocument | None:
        raise NotImplementedError

    def list_documents(self) -> list[KnowledgeDocument]:
        raise NotImplementedError

    def add_case(self, case: KnowledgeCase) -> None:
        raise NotImplementedError

    def update_case(self, case: KnowledgeCase) -> None:
        raise NotImplementedError

    def archive_case(self, case_id: CaseId) -> None:
        raise NotImplementedError

    def get_case(self, case_id: CaseId) -> KnowledgeCase | None:
        raise NotImplementedError

    def list_cases(self) -> list[KnowledgeCase]:
        raise NotImplementedError

    def link_document_to_case(self, document_id: DocumentId, case_id: CaseId) -> None:
        raise NotImplementedError

    def unlink_document_from_case(self, document_id: DocumentId, case_id: CaseId) -> None:
        raise NotImplementedError

    def list_documents_for_case(self, case_id: CaseId) -> list[DocumentId]:
        raise NotImplementedError
