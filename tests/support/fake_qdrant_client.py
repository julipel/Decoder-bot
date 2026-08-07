"""
`FakeAsyncQdrantClient` — duck-typed фейк `AsyncQdrantClient` (Sprint 8,
задача S8-05) для admin REST-тестов документов, где недоступен реальный
Qdrant-сервер: подставляется через `app.dependency_overrides[get_qdrant_client]`
в `create_application()`-приложении с реальным lifespan, так что
`QdrantVectorRepository` (реальная реализация, ADR-6.2) действительно
вызывает `upsert`/`delete`/`query_points` — но против in-memory
хранилища, не сети.

Принимает и хранит РЕАЛЬНЫЕ объекты `qdrant_client.models.PointStruct`/
`FilterSelector`, которые строит production-код (`QdrantVectorRepository`)
— фейк не переопределяет их структуру, только читает нужные атрибуты.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class _QueryPointsResponse:
    points: list[Any] = field(default_factory=list)


class FakeAsyncQdrantClient:
    def __init__(self, *, get_collections_should_fail: bool = False) -> None:
        self.points: dict[str, Any] = {}
        self.upsert_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []
        self._get_collections_should_fail = get_collections_should_fail

    async def upsert(self, collection_name: str, points: list[Any]) -> None:
        self.upsert_calls.append({"collection_name": collection_name, "points": list(points)})
        for point in points:
            self.points[str(point.id)] = point

    async def delete(self, collection_name: str, points_selector: Any) -> None:
        self.delete_calls.append({"collection_name": collection_name})
        match_value = points_selector.filter.must[0].match.value
        to_remove = [
            point_id for point_id, point in self.points.items() if point.payload.get("document_id") == match_value
        ]
        for point_id in to_remove:
            del self.points[point_id]

    async def query_points(
        self,
        collection_name: str,
        query: list[float],
        limit: int,
        score_threshold: float,
        query_filter: Any,
        with_payload: bool,
    ) -> _QueryPointsResponse:
        return _QueryPointsResponse(points=[])

    async def close(self) -> None:
        return None

    async def get_collections(self) -> object:
        """Sprint 8, S8-09 — используется `QdrantHealthCheck.check()`; успех по умолчанию, не выбрасывает исключений."""
        if self._get_collections_should_fail:
            raise RuntimeError("FakeAsyncQdrantClient: имитация недоступности Qdrant")
        return object()
