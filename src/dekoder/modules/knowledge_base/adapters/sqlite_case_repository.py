"""SQLite-реализация CaseRepositoryPort, включая таблицу связей «документ—кейс»."""

from __future__ import annotations

from dekoder.infrastructure.sqlite.connection import SqliteConnectionFactory
from dekoder.modules.knowledge_base.application.ports import CaseRepositoryPort
from dekoder.modules.knowledge_base.domain.case import Case
from dekoder.shared.domain.identifiers import CaseId, DocumentId


class SqliteCaseRepository(CaseRepositoryPort):
    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def add(self, case: Case) -> None:
        raise NotImplementedError

    def update(self, case: Case) -> None:
        raise NotImplementedError

    def archive(self, case_id: CaseId) -> None:
        raise NotImplementedError

    def get(self, case_id: CaseId) -> Case | None:
        raise NotImplementedError

    def list_all(self) -> list[Case]:
        raise NotImplementedError

    def link_document(self, case_id: CaseId, document_id: DocumentId) -> None:
        raise NotImplementedError

    def unlink_document(self, case_id: CaseId, document_id: DocumentId) -> None:
        raise NotImplementedError

    def list_documents_for_case(self, case_id: CaseId) -> list[DocumentId]:
        raise NotImplementedError
