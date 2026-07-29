"""Оркестрация кейсов и связей «документ—кейс» (docs/01, §3, сценарии 9–10)."""

from __future__ import annotations

from dekoder.modules.knowledge_base.application.ports import CaseRepositoryPort
from dekoder.modules.knowledge_base.domain.case import Case
from dekoder.modules.logging_audit.application.ports import AuditPort
from dekoder.modules.search.application.ports import IndexingPort
from dekoder.shared.domain.identifiers import CaseId, DocumentId


class CreateCaseUseCase:
    def __init__(self, case_repository: CaseRepositoryPort, indexing: IndexingPort, audit: AuditPort) -> None:
        self._case_repository = case_repository
        self._indexing = indexing
        self._audit = audit

    def execute(self, case: Case) -> None:
        raise NotImplementedError


class UpdateCaseUseCase:
    def __init__(self, case_repository: CaseRepositoryPort, indexing: IndexingPort, audit: AuditPort) -> None:
        self._case_repository = case_repository
        self._indexing = indexing
        self._audit = audit

    def execute(self, case: Case) -> None:
        raise NotImplementedError


class ArchiveCaseUseCase:
    def __init__(self, case_repository: CaseRepositoryPort, audit: AuditPort) -> None:
        self._case_repository = case_repository
        self._audit = audit

    def execute(self, case_id: CaseId) -> None:
        raise NotImplementedError


class LinkDocumentToCaseUseCase:
    def __init__(self, case_repository: CaseRepositoryPort, audit: AuditPort) -> None:
        self._case_repository = case_repository
        self._audit = audit

    def execute(self, case_id: CaseId, document_id: DocumentId) -> None:
        raise NotImplementedError
