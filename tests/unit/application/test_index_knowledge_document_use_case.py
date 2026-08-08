"""Тесты `IndexKnowledgeDocumentUseCase` (Sprint 6, задача S6-06, §14.4/14.11/14.12)."""

from __future__ import annotations

import json

import pytest
from tests.support.fake_knowledge_repositories import (
    FakeDocumentStorage,
    FakeEmbeddingProvider,
    FakeKnowledgeDocumentRepository,
    FakeVectorRepository,
)

from dekoder.application.knowledge.dto import IndexDocumentCommand
from dekoder.application.knowledge.use_cases.index_document import IndexKnowledgeDocumentUseCase
from dekoder.domain.knowledge.value_objects import DocumentStatus, DocumentType
from dekoder.infrastructure.documents.chunking.structural_chunker import StructuralChunker
from dekoder.infrastructure.documents.parsers.markdown_parser import MarkdownParser
from dekoder.infrastructure.documents.parsers.pdf_parser import PdfParser
from dekoder.infrastructure.documents.parsers.txt_parser import TxtParser
from dekoder.shared.errors import ValidationError
from dekoder.shared.logging import configure_logging


def _read_last_log_line(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "ожидалась хотя бы одна строка журнала"
    return json.loads(out[-1])


_PARSERS = {
    DocumentType.TXT: TxtParser(),
    DocumentType.MARKDOWN: MarkdownParser(),
    DocumentType.PDF: PdfParser(),
}


def _make_use_case(
    *,
    document_repository: FakeKnowledgeDocumentRepository | None = None,
    document_storage: FakeDocumentStorage | None = None,
    embedding_provider: FakeEmbeddingProvider | None = None,
    vector_repository: FakeVectorRepository | None = None,
    max_file_size_bytes: int = 20_000_000,
) -> tuple[IndexKnowledgeDocumentUseCase, FakeKnowledgeDocumentRepository, FakeDocumentStorage, FakeVectorRepository]:
    document_repository = document_repository or FakeKnowledgeDocumentRepository()
    document_storage = document_storage or FakeDocumentStorage()
    embedding_provider = embedding_provider or FakeEmbeddingProvider()
    vector_repository = vector_repository or FakeVectorRepository()
    use_case = IndexKnowledgeDocumentUseCase(
        document_repository=document_repository,
        document_storage=document_storage,
        parsers=_PARSERS,
        chunker=StructuralChunker(chunk_size=200, chunk_overlap=20),
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        max_file_size_bytes=max_file_size_bytes,
    )
    return use_case, document_repository, document_storage, vector_repository


class TestSuccessfulIndexing:
    async def test_txt_document_ends_up_indexed_with_chunks_upserted(self) -> None:
        use_case, document_repository, document_storage, vector_repository = _make_use_case()
        command = IndexDocumentCommand(
            title="Заметка", source_filename="note.txt", content="Абзац один.\n\nАбзац два.".encode()
        )

        result = await use_case.execute(command)

        assert result.document.status is DocumentStatus.INDEXED
        assert result.document.document_type is DocumentType.TXT
        assert result.document.chunk_count == 1
        assert result.document.error_message is None
        assert result.document.indexed_at is not None
        assert await document_repository.get_by_id(result.document.id) == result.document
        assert document_storage.saved[result.document.id] == command.content
        assert len(vector_repository.chunks_by_document[result.document.id]) == 1

    async def test_reindexing_identical_content_reuses_same_document_id(self) -> None:
        use_case, document_repository, _, vector_repository = _make_use_case()
        content = b"Identical content for dedup test."
        first = await use_case.execute(IndexDocumentCommand(title="v1", source_filename="a.txt", content=content))
        second = await use_case.execute(IndexDocumentCommand(title="v2", source_filename="a.txt", content=content))

        assert first.document.id == second.document.id
        assert second.document.title == "v2"
        # delete_by_document вызывается перед upsert на КАЖДОЙ индексации,
        # не только при повторной (ADR-6.9) — на первой это no-op (нет
        # старых точек), поэтому вызовов два, оба с одним document_id.
        assert vector_repository.deleted_documents == [first.document.id, first.document.id]
        stored = await document_repository.get_by_checksum(second.document.checksum)
        assert stored is not None
        assert stored.id == first.document.id


class TestUnsupportedInput:
    async def test_unknown_extension_raises_without_creating_a_document(self) -> None:
        use_case, document_repository, _, _ = _make_use_case()

        with pytest.raises(ValidationError) as exc_info:
            await use_case.execute(IndexDocumentCommand(title="x", source_filename="file.exe", content=b"data"))

        assert exc_info.value.code == "KNOWLEDGE_DOCUMENT_UNSUPPORTED_FORMAT"
        assert await document_repository.get_by_checksum("anything") is None

    async def test_oversized_file_raises_without_creating_a_document(self) -> None:
        use_case, document_repository, _, _ = _make_use_case(max_file_size_bytes=10)

        with pytest.raises(ValidationError) as exc_info:
            await use_case.execute(
                IndexDocumentCommand(title="x", source_filename="big.txt", content=b"way more than ten bytes")
            )

        assert exc_info.value.code == "KNOWLEDGE_DOCUMENT_TOO_LARGE"

    async def test_content_without_text_layer_marks_document_unsupported_not_raise(self) -> None:
        use_case, _, _, vector_repository = _make_use_case()

        result = await use_case.execute(
            IndexDocumentCommand(title="Пустой", source_filename="empty.txt", content=b"   \n\n  ")
        )

        assert result.document.status is DocumentStatus.UNSUPPORTED
        assert result.document.chunk_count == 0
        assert result.document.error_message is not None
        assert result.document.id not in vector_repository.chunks_by_document


class TestPipelineFailure:
    async def test_embedding_provider_failure_marks_document_failed_not_raise(self) -> None:
        use_case, _, _, vector_repository = _make_use_case(embedding_provider=FakeEmbeddingProvider(fail=True))

        result = await use_case.execute(
            IndexDocumentCommand(title="Заметка", source_filename="note.txt", content=b"Some content here.")
        )

        assert result.document.status is DocumentStatus.FAILED
        assert result.document.chunk_count == 0
        assert "имитация сбоя" in (result.document.error_message or "")
        assert vector_repository.deleted_documents == []


class TestIndexKnowledgeDocumentAuditLog:
    """Sprint 9, S9-04 (ADR-9.4): knowledge_document_indexed переведён на log_audit_event()."""

    async def test_logs_indexed_event_marked_as_audit(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        use_case, _, _, _ = _make_use_case()

        result = await use_case.execute(
            IndexDocumentCommand(title="Заметка", source_filename="note.txt", content=b"Some content here.")
        )

        entry = _read_last_log_line(capsys)
        assert entry["event"] == "knowledge_document_indexed"
        assert entry["document_id"] == str(result.document.id)
        assert entry["chunk_count"] == result.document.chunk_count
        assert entry["audit"] is True
