"""Тесты `ListKnowledgeDocumentsUseCase` (Sprint 8, задача S8-04, ADR-8.5)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from tests.support.fake_knowledge_repositories import FakeKnowledgeDocumentRepository

from dekoder.application.knowledge.use_cases.list_documents import ListKnowledgeDocumentsUseCase
from dekoder.domain.knowledge.entities import KnowledgeDocument
from dekoder.domain.knowledge.value_objects import DocumentStatus, DocumentType


def _make_document(status: DocumentStatus, checksum: str) -> KnowledgeDocument:
    now = datetime.now(UTC)
    return KnowledgeDocument(
        id=uuid4(),
        title="Документ",
        document_type=DocumentType.TXT,
        source_filename="doc.txt",
        checksum=checksum,
        status=status,
        tags=(),
        description=None,
        chunk_count=0,
        error_message=None,
        created_at=now,
        updated_at=now,
        indexed_at=None,
    )


class TestListKnowledgeDocuments:
    async def test_returns_documents_of_every_status_including_failures(self) -> None:
        repository = FakeKnowledgeDocumentRepository()
        indexed = _make_document(DocumentStatus.INDEXED, "checksum-indexed")
        failed = _make_document(DocumentStatus.FAILED, "checksum-failed")
        unsupported = _make_document(DocumentStatus.UNSUPPORTED, "checksum-unsupported")
        for document in (indexed, failed, unsupported):
            await repository.save(document)

        use_case = ListKnowledgeDocumentsUseCase(document_repository=repository)
        result = await use_case.execute()

        assert {document.id for document in result} == {indexed.id, failed.id, unsupported.id}

    async def test_empty_catalog_returns_empty_sequence(self) -> None:
        use_case = ListKnowledgeDocumentsUseCase(document_repository=FakeKnowledgeDocumentRepository())

        result = await use_case.execute()

        assert list(result) == []
