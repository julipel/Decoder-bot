"""
Тесты `ReindexKnowledgeDocumentUseCase` (Sprint 8, задача S8-04, ADR-8.6)
— переиспользует реальный `IndexKnowledgeDocumentUseCase` поверх
fake-репозиториев/парсеров/чанкера (тот же стиль, что
`test_index_knowledge_document_use_case.py`), не мокает делегирование.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from tests.support.fake_knowledge_repositories import (
    FakeDocumentStorage,
    FakeEmbeddingProvider,
    FakeKnowledgeDocumentRepository,
    FakeVectorRepository,
)

from dekoder.application.knowledge.dto import IndexDocumentCommand
from dekoder.application.knowledge.use_cases.index_document import IndexKnowledgeDocumentUseCase
from dekoder.application.knowledge.use_cases.reindex_document import ReindexKnowledgeDocumentUseCase
from dekoder.domain.knowledge.value_objects import DocumentStatus, DocumentType
from dekoder.infrastructure.documents.chunking.structural_chunker import StructuralChunker
from dekoder.infrastructure.documents.parsers.txt_parser import TxtParser
from dekoder.shared.logging import configure_logging

_PARSERS = {DocumentType.TXT: TxtParser()}


def _find_log_entry(capsys: pytest.CaptureFixture[str], event: str) -> dict[str, object]:
    lines = capsys.readouterr().out.strip().splitlines()
    entries = [json.loads(line) for line in lines]
    matches = [entry for entry in entries if entry.get("event") == event]
    assert matches, f"ожидалось событие {event!r} в журнале, получено: {entries!r}"
    return matches[-1]


def _make_reindex_use_case() -> tuple[
    ReindexKnowledgeDocumentUseCase,
    IndexKnowledgeDocumentUseCase,
    FakeKnowledgeDocumentRepository,
    FakeDocumentStorage,
    FakeVectorRepository,
]:
    document_repository = FakeKnowledgeDocumentRepository()
    document_storage = FakeDocumentStorage()
    vector_repository = FakeVectorRepository()
    index_use_case = IndexKnowledgeDocumentUseCase(
        document_repository=document_repository,
        document_storage=document_storage,
        parsers=_PARSERS,
        chunker=StructuralChunker(chunk_size=200, chunk_overlap=20),
        embedding_provider=FakeEmbeddingProvider(),
        vector_repository=vector_repository,
        max_file_size_bytes=20_000_000,
    )
    reindex_use_case = ReindexKnowledgeDocumentUseCase(
        document_repository=document_repository,
        document_storage=document_storage,
        index_use_case=index_use_case,
    )
    return reindex_use_case, index_use_case, document_repository, document_storage, vector_repository


class TestReindexKnowledgeDocument:
    async def test_reindexing_unchanged_content_keeps_same_document_id(self) -> None:
        reindex_use_case, index_use_case, _, document_storage, _ = _make_reindex_use_case()
        original = await index_use_case.execute(
            IndexDocumentCommand(title="Заметка", source_filename="note.txt", content=b"Abzac odin.")
        )
        assert document_storage.saved[original.document.id] == b"Abzac odin."

        result = await reindex_use_case.execute(original.document.id)

        assert result is not None
        assert result.document.id == original.document.id
        assert result.document.status is DocumentStatus.INDEXED

    async def test_reindexing_recomputes_chunk_count(self) -> None:
        reindex_use_case, index_use_case, _, _, vector_repository = _make_reindex_use_case()
        original = await index_use_case.execute(
            IndexDocumentCommand(title="Заметка", source_filename="note.txt", content=b"Abzac odin.\n\nAbzac dva.")
        )

        result = await reindex_use_case.execute(original.document.id)

        assert result is not None
        assert result.document.chunk_count == len(vector_repository.chunks_by_document[original.document.id])

    async def test_reindexing_unknown_document_returns_none(self) -> None:
        reindex_use_case, _, _, _, _ = _make_reindex_use_case()

        result = await reindex_use_case.execute(uuid4())

        assert result is None

    async def test_reindex_does_not_re_upload_bytes_reads_existing_storage(self) -> None:
        reindex_use_case, index_use_case, _, document_storage, _ = _make_reindex_use_case()
        original = await index_use_case.execute(
            IndexDocumentCommand(title="Заметка", source_filename="note.txt", content=b"Original bytes.")
        )
        read_calls_before = document_storage.saved.copy()

        result = await reindex_use_case.execute(original.document.id)

        assert result is not None
        # Байты не поменялись — reindex прочитал те же сохранённые данные, не запросил новую загрузку.
        assert document_storage.saved == read_calls_before


class TestReindexKnowledgeDocumentAuditLog:
    """Sprint 9, S9-04 (ADR-9.4): knowledge_document_reindex_requested переведён на log_audit_event()."""

    async def test_logs_reindex_requested_event_marked_as_audit(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        reindex_use_case, index_use_case, _, _, _ = _make_reindex_use_case()
        original = await index_use_case.execute(
            IndexDocumentCommand(title="Заметка", source_filename="note.txt", content=b"Abzac odin.")
        )
        capsys.readouterr()  # сбрасываем логи индексации исходного документа

        await reindex_use_case.execute(original.document.id)

        entry = _find_log_entry(capsys, "knowledge_document_reindex_requested")
        assert entry["document_id"] == str(original.document.id)
        assert entry["audit"] is True
