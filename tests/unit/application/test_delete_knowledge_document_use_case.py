"""Тесты `DeleteKnowledgeDocumentUseCase` (Sprint 6, задача S6-06, §14.12)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from tests.support.fake_knowledge_repositories import (
    FakeDocumentStorage,
    FakeKnowledgeDocumentRepository,
    FakeVectorRepository,
)

from dekoder.application.knowledge.use_cases.delete_document import DeleteKnowledgeDocumentUseCase
from dekoder.domain.knowledge.entities import KnowledgeDocument
from dekoder.domain.knowledge.value_objects import DocumentStatus, DocumentType


def _make_document() -> KnowledgeDocument:
    now = datetime.now(UTC)
    return KnowledgeDocument(
        id=uuid4(),
        title="Документ",
        document_type=DocumentType.TXT,
        source_filename="doc.txt",
        checksum="abc123",
        status=DocumentStatus.INDEXED,
        tags=(),
        description=None,
        chunk_count=3,
        error_message=None,
        created_at=now,
        updated_at=now,
        indexed_at=now,
    )


class TestDeleteKnowledgeDocument:
    async def test_deletes_vectors_file_and_metadata_row(self) -> None:
        document_repository = FakeKnowledgeDocumentRepository()
        document_storage = FakeDocumentStorage()
        vector_repository = FakeVectorRepository()
        document = _make_document()
        await document_repository.save(document)
        await document_storage.save(document.id, b"content")

        use_case = DeleteKnowledgeDocumentUseCase(
            document_repository=document_repository,
            document_storage=document_storage,
            vector_repository=vector_repository,
        )
        await use_case.execute(document.id)

        assert vector_repository.deleted_documents == [document.id]
        assert document.id not in document_storage.saved
        assert await document_repository.get_by_id(document.id) is None

    async def test_deleting_unknown_document_is_idempotent(self) -> None:
        document_repository = FakeKnowledgeDocumentRepository()
        document_storage = FakeDocumentStorage()
        vector_repository = FakeVectorRepository()
        use_case = DeleteKnowledgeDocumentUseCase(
            document_repository=document_repository,
            document_storage=document_storage,
            vector_repository=vector_repository,
        )

        await use_case.execute(uuid4())  # не должно поднимать исключение
