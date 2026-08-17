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

Sprint 10 (задача S10-02, ADR-10.2): `query_points()` дорабатывается до
реального косинусного поиска по `self.points`, с фильтрацией по
`document_id`/`tags` — ровно то подмножество `models.Filter`, которое
строит `QdrantVectorRepository._build_filter()` (только `must`-условия,
`MatchAny`). Раньше метод безусловно возвращал `points=[]` — структурно
не мог подтвердить, что RAG-поиск (Сценарий 5, §18.4) что-то находит.
Сигнатура метода и поведение `upsert`/`delete`/`get_collections` не
меняются — только тело `query_points()` и два новых приватных хелпера.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _QueryPointsResponse:
    points: list[Any] = field(default_factory=list)


@dataclass
class _FakeScoredPoint:
    """
    Форма, которую ожидает production `_to_search_result()`
    (`infrastructure/qdrant/vector_repository.py`) — только `score`/
    `payload`, ничего больше не читается вызывающим кодом.
    """

    score: float
    payload: dict[str, Any]


def _matches_filter(point: Any, query_filter: Any) -> bool:
    """
    Понимает ровно то, что строит `QdrantVectorRepository._build_filter()`
    — `Filter(must=[FieldCondition(key=..., match=MatchAny(any=[...]))])`
    по `document_id`/`tags`, не универсальный движок фильтрации. Без
    фильтра (`query_filter is None`) — любая точка проходит.
    """
    if query_filter is None or not query_filter.must:
        return True
    payload = point.payload or {}
    for condition in query_filter.must:
        allowed = set(condition.match.any)
        value = payload.get(condition.key)
        if isinstance(value, list):
            if not (set(value) & allowed):
                return False
        elif value not in allowed:
            return False
    return True


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Стандартная косинусная близость без внешних зависимостей (без `numpy`, ADR-10.2)."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


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
        candidates = [point for point in self.points.values() if _matches_filter(point, query_filter)]
        scored = [(point, _cosine_similarity(query, list(point.vector))) for point in candidates]
        scored = [(point, score) for point, score in scored if score >= score_threshold]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return _QueryPointsResponse(
            points=[_FakeScoredPoint(score=score, payload=point.payload or {}) for point, score in scored[:limit]]
        )

    async def close(self) -> None:
        return None

    async def get_collections(self) -> object:
        """Sprint 8, S8-09 — используется `QdrantHealthCheck.check()`; успех по умолчанию, не выбрасывает исключений."""
        if self._get_collections_should_fail:
            raise RuntimeError("FakeAsyncQdrantClient: имитация недоступности Qdrant")
        return object()
