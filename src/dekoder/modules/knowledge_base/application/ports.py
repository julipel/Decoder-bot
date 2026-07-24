"""
Порты базы знаний (docs/02, §7).

FileStoragePort не назван по имени в docs/02, но прямо следует из уже
описанного там разделения хранения (оригиналы файлов отдельно от
метаданных в SQLite, docs/01 §4.6) — см. docs/03, раздел «Замечания».
"""

from __future__ import annotations

from typing import Protocol

from dekoder.shared.domain.identifiers import CaseId, DocumentId
from dekoder.modules.knowledge_base.domain.case import Case
from dekoder.modules.knowledge_base.domain.document import Document


class DocumentRepositoryPort(Protocol):
    """CRUD метаданных документа (docs/02, §7)."""

    def add(self, document: Document) -> None: ...

    def update(self, document: Document) -> None: ...

    def delete(self, document_id: DocumentId) -> None: ...

    def get(self, document_id: DocumentId) -> Document | None: ...

    def list_all(self) -> list[Document]: ...


class CaseRepositoryPort(Protocol):
    """CRUD кейсов и связей «документ—кейс» (docs/02, §7)."""

    def add(self, case: Case) -> None: ...

    def update(self, case: Case) -> None: ...

    def archive(self, case_id: CaseId) -> None: ...

    def get(self, case_id: CaseId) -> Case | None: ...

    def list_all(self) -> list[Case]: ...

    def link_document(self, case_id: CaseId, document_id: DocumentId) -> None: ...

    def unlink_document(self, case_id: CaseId, document_id: DocumentId) -> None: ...

    def list_documents_for_case(self, case_id: CaseId) -> list[DocumentId]: ...


class FileStoragePort(Protocol):
    """
    Оригиналы файлов документов (docs/01, §4.6: «файловое хранилище»
    отдельно от метаданных в SQLite). Введён архитектором как прямое
    следствие уже принятого решения — см. docs/03.
    """

    def save(self, document_id: DocumentId, content: bytes) -> None: ...

    def read(self, document_id: DocumentId) -> bytes: ...

    def delete(self, document_id: DocumentId) -> None: ...
