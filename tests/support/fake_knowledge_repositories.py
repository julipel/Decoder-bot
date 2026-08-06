"""
In-memory fake-реализации портов базы знаний
(`application/knowledge/ports.py`) — общий тестовый helper для
`IndexKnowledgeDocumentUseCase`/`DeleteKnowledgeDocumentUseCase`/
`SemanticSearchService` (Sprint 6, задачи S6-06/S6-07).

Тот же приём, что и `tests/support/fake_conversation_repositories.py`:
только словари в памяти, без SQLAlchemy/Qdrant/httpx. Реальные парсеры и
чанкер (`infrastructure/documents/`) переиспользуются в тестах как есть —
они чистые и быстрые, подменять их fake-реализациями смысла нет.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from dekoder.application.knowledge.pipeline import EmbeddedChunk
from dekoder.domain.knowledge.entities import KnowledgeDocument
from dekoder.domain.knowledge.search import SearchResult
from dekoder.shared.errors import InfrastructureError


class FakeKnowledgeDocumentRepository:
    """In-memory fake порта `KnowledgeDocumentRepository`."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, KnowledgeDocument] = {}

    async def save(self, document: KnowledgeDocument) -> KnowledgeDocument:
        self._by_id[document.id] = document
        return document

    async def get_by_id(self, document_id: UUID) -> KnowledgeDocument | None:
        return self._by_id.get(document_id)

    async def get_by_checksum(self, checksum: str) -> KnowledgeDocument | None:
        for document in self._by_id.values():
            if document.checksum == checksum:
                return document
        return None

    async def update(self, document: KnowledgeDocument) -> KnowledgeDocument:
        self._by_id[document.id] = document
        return document

    async def delete(self, document_id: UUID) -> None:
        self._by_id.pop(document_id, None)


class FakeDocumentStorage:
    """In-memory fake порта `DocumentStorage`."""

    def __init__(self) -> None:
        self.saved: dict[UUID, bytes] = {}

    async def save(self, document_id: UUID, content: bytes) -> None:
        self.saved[document_id] = content

    async def read(self, document_id: UUID) -> bytes:
        if document_id not in self.saved:
            raise InfrastructureError(
                message=f"FakeDocumentStorage: файл документа {document_id} не найден",
                user_message="Не удалось прочитать документ.",
                code="KNOWLEDGE_DOCUMENT_FILE_READ_FAILED",
            )
        return self.saved[document_id]

    async def delete(self, document_id: UUID) -> None:
        self.saved.pop(document_id, None)


class FakeEmbeddingProvider:
    """In-memory fake порта `EmbeddingProvider` — детерминированные векторы по индексу входного текста."""

    def __init__(self, vector_size: int = 3, *, fail: bool = False) -> None:
        self._vector_size = vector_size
        self._fail = fail
        self.embed_calls: list[list[str]] = []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self._fail:
            raise RuntimeError("FakeEmbeddingProvider: имитация сбоя провайдера эмбеддингов")
        self.embed_calls.append(list(texts))
        return [[float(index)] * self._vector_size for index, _ in enumerate(texts)]


class FakeVectorRepository:
    """In-memory fake порта `VectorRepository` — фрагменты по документу и настраиваемый результат `search`."""

    def __init__(self, search_results: list[SearchResult] | None = None) -> None:
        self.chunks_by_document: dict[UUID, list[EmbeddedChunk]] = {}
        self.deleted_documents: list[UUID] = []
        self.search_calls: list[dict[str, Any]] = []
        self._search_results = search_results or []

    async def upsert_chunks(self, document: KnowledgeDocument, chunks: list[EmbeddedChunk]) -> None:
        self.chunks_by_document.setdefault(document.id, []).extend(chunks)

    async def search(
        self,
        query_vector: list[float],
        *,
        limit: int,
        min_score: float,
        document_ids: list[UUID] | None = None,
        tags: list[str] | None = None,
    ) -> list[SearchResult]:
        self.search_calls.append(
            {
                "query_vector": list(query_vector),
                "limit": limit,
                "min_score": min_score,
                "document_ids": document_ids,
                "tags": tags,
            }
        )
        return list(self._search_results)

    async def delete_by_document(self, document_id: UUID) -> None:
        self.deleted_documents.append(document_id)
        self.chunks_by_document.pop(document_id, None)
