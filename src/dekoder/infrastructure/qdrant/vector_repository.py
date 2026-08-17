"""
`QdrantVectorRepository` — реализация `VectorRepository` (Sprint 6,
задача S6-05, ADR-6.2) поверх `AsyncQdrantClient`.

Единственное хранилище текста и векторов фрагментов (ADR-6.2) — payload
каждой точки несёт полный набор метаданных §14.5 («Плана реализации.md»)
и сам текст фрагмента (иначе `search()` не смог бы вернуть готовый текст
без второго обращения к SQL, которого для фрагментов вообще не существует).

Точки — со случайным `uuid4()`, не детерминированным `document_id` +
`chunk_index`: переиндексация всегда идёт через явный `delete_by_document`
перед `upsert_chunks` (ADR-6.9, `IndexKnowledgeDocumentUseCase`), поэтому
устойчивый к повторной записи ID не нужен.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from qdrant_client import AsyncQdrantClient, models

from dekoder.application.knowledge.pipeline import EmbeddedChunk
from dekoder.domain.knowledge.entities import KnowledgeDocument
from dekoder.domain.knowledge.search import SearchResult, SourceReference
from dekoder.shared.errors import InfrastructureError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


class QdrantVectorRepository:
    def __init__(self, client: AsyncQdrantClient, collection_name: str) -> None:
        self._client = client
        self._collection_name = collection_name

    async def upsert_chunks(self, document: KnowledgeDocument, chunks: Sequence[EmbeddedChunk]) -> None:
        if not chunks:
            return

        indexed_at = datetime.now(UTC).isoformat()
        points = [
            models.PointStruct(
                id=str(uuid4()),
                vector=list(chunk.vector),
                payload={
                    "document_id": str(document.id),
                    "document_title": document.title,
                    "document_type": document.document_type.value,
                    "chunk_index": chunk.chunk_index,
                    "section_title": chunk.section_title,
                    "page_number": chunk.page_number,
                    "tags": list(document.tags),
                    "checksum": document.checksum,
                    "indexed_at": indexed_at,
                    "text": chunk.text,
                },
            )
            for chunk in chunks
        ]
        try:
            await self._client.upsert(collection_name=self._collection_name, points=points)
        except Exception as exc:
            _logger.error("qdrant_upsert_failed", document_id=str(document.id), error=str(exc))
            raise InfrastructureError(
                message=f"Не удалось сохранить фрагменты документа {document.id} в Qdrant: {exc}",
                user_message="Не удалось проиндексировать документ, попробуйте позже.",
                code="QDRANT_UPSERT_FAILED",
                cause=exc,
            ) from exc

    async def search(
        self,
        query_vector: Sequence[float],
        *,
        limit: int,
        min_score: float,
        document_ids: Sequence[UUID] | None = None,
        tags: Sequence[str] | None = None,
    ) -> list[SearchResult]:
        try:
            response = await self._client.query_points(
                collection_name=self._collection_name,
                query=list(query_vector),
                limit=limit,
                score_threshold=min_score,
                query_filter=_build_filter(document_ids, tags),
                with_payload=True,
            )
        except Exception as exc:
            _logger.error("qdrant_search_failed", error=str(exc))
            raise InfrastructureError(
                message=f"Не удалось выполнить поиск в Qdrant: {exc}",
                user_message="Не удалось выполнить поиск по базе знаний, попробуйте позже.",
                code="QDRANT_SEARCH_FAILED",
                cause=exc,
            ) from exc
        return [_to_search_result(point) for point in response.points]

    async def delete_by_document(self, document_id: UUID) -> None:
        try:
            await self._client.delete(
                collection_name=self._collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=str(document_id)))]
                    )
                ),
            )
        except Exception as exc:
            _logger.error("qdrant_delete_by_document_failed", document_id=str(document_id), error=str(exc))
            raise InfrastructureError(
                message=f"Не удалось удалить векторы документа {document_id} из Qdrant: {exc}",
                user_message="Не удалось удалить документ, попробуйте позже.",
                code="QDRANT_DELETE_FAILED",
                cause=exc,
            ) from exc


def _build_filter(document_ids: Sequence[UUID] | None, tags: Sequence[str] | None) -> models.Filter | None:
    conditions: list[models.FieldCondition] = []
    if document_ids:
        ids = [str(doc_id) for doc_id in document_ids]
        conditions.append(models.FieldCondition(key="document_id", match=models.MatchAny(any=ids)))
    if tags:
        conditions.append(models.FieldCondition(key="tags", match=models.MatchAny(any=list(tags))))
    return models.Filter(must=list(conditions)) if conditions else None


def _to_search_result(point: models.ScoredPoint) -> SearchResult:
    payload: dict[str, Any] = point.payload or {}
    return SearchResult(
        text=str(payload.get("text", "")),
        score=point.score,
        source=SourceReference(
            document_id=UUID(str(payload.get("document_id"))),
            document_title=str(payload.get("document_title", "")),
            chunk_index=int(payload.get("chunk_index", 0)),
            section_title=payload.get("section_title"),
            page_number=payload.get("page_number"),
        ),
    )
