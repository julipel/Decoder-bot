"""Тесты `GetKnowledgeDocumentUseCase` (Sprint 8, задача S8-04, ADR-8.5)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from tests.support.fake_knowledge_repositories import FakeKnowledgeDocumentRepository

from dekoder.application.knowledge.use_cases.get_document import GetKnowledgeDocumentUseCase
from dekoder.domain.knowledge.entities import KnowledgeDocument
from dekoder.domain.knowledge.value_objects import DocumentStatus, DocumentType


def _make_document() -> KnowledgeDocument:
    now = datetime.now(UTC)
    return KnowledgeDocument(
        id=uuid4(),
        title="Документ",
        document_type=DocumentType.TXT,
        source_filename="doc.txt",
        checksum="checksum",
        status=DocumentStatus.INDEXED,
        tags=(),
        description=None,
        chunk_count=1,
        error_message=None,
        created_at=now,
        updated_at=now,
        indexed_at=now,
    )


class TestGetKnowledgeDocument:
    async def test_returns_existing_document(self) -> None:
        repository = FakeKnowledgeDocumentRepository()
        document = _make_document()
        await repository.save(document)

        use_case = GetKnowledgeDocumentUseCase(document_repository=repository)
        result = await use_case.execute(document.id)

        assert result == document

    async def test_returns_none_for_unknown_id(self) -> None:
        use_case = GetKnowledgeDocumentUseCase(document_repository=FakeKnowledgeDocumentRepository())

        result = await use_case.execute(uuid4())

        assert result is None
