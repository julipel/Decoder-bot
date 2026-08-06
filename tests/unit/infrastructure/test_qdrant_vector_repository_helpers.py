"""
Тесты чистых функций `infrastructure/qdrant/vector_repository.py`
(`_build_filter`/`_to_search_result`, Sprint 6, задача S6-05/S6-10) —
без реального Qdrant: `QdrantVectorRepository` сам (методы, делающие
сетевые вызовы через `AsyncQdrantClient`) проверяется Docker-based
E2E-проверкой Sprint 6 (задача S6-11), не unit-тестами.
"""

from __future__ import annotations

from uuid import uuid4

from qdrant_client import models
from qdrant_client.http.models.models import ScoredPoint

from dekoder.infrastructure.qdrant.vector_repository import _build_filter, _to_search_result


class TestBuildFilter:
    def test_returns_none_without_document_ids_or_tags(self) -> None:
        assert _build_filter(None, None) is None
        assert _build_filter([], []) is None

    def test_builds_document_id_match_any_condition(self) -> None:
        document_ids = [uuid4(), uuid4()]

        result = _build_filter(document_ids, None)

        assert result is not None
        assert result.must is not None
        condition = result.must[0]
        assert isinstance(condition, models.FieldCondition)
        assert condition.key == "document_id"
        assert isinstance(condition.match, models.MatchAny)
        assert set(condition.match.any) == {str(doc_id) for doc_id in document_ids}

    def test_builds_tags_match_any_condition(self) -> None:
        result = _build_filter(None, ["гарантия", "поддержка"])

        assert result is not None
        assert result.must is not None
        condition = result.must[0]
        assert condition.key == "tags"
        assert isinstance(condition.match, models.MatchAny)
        assert set(condition.match.any) == {"гарантия", "поддержка"}

    def test_combines_document_ids_and_tags_conditions(self) -> None:
        document_id = uuid4()

        result = _build_filter([document_id], ["гарантия"])

        assert result is not None
        assert result.must is not None
        assert len(result.must) == 2


class TestToSearchResult:
    def test_builds_search_result_from_scored_point_payload(self) -> None:
        document_id = uuid4()
        point = ScoredPoint(
            id=str(uuid4()),
            version=1,
            score=0.87,
            payload={
                "text": "Гарантия действует 24 месяца.",
                "document_id": str(document_id),
                "document_title": "Условия гарантии",
                "chunk_index": 2,
                "section_title": "Гарантийные обязательства",
                "page_number": 5,
            },
        )

        result = _to_search_result(point)

        assert result.text == "Гарантия действует 24 месяца."
        assert result.score == 0.87
        assert result.source.document_id == document_id
        assert result.source.document_title == "Условия гарантии"
        assert result.source.chunk_index == 2
        assert result.source.section_title == "Гарантийные обязательства"
        assert result.source.page_number == 5

    def test_handles_missing_optional_payload_fields(self) -> None:
        document_id = uuid4()
        point = ScoredPoint(
            id=str(uuid4()),
            version=1,
            score=0.5,
            payload={"text": "Текст.", "document_id": str(document_id), "document_title": "Документ", "chunk_index": 0},
        )

        result = _to_search_result(point)

        assert result.source.section_title is None
        assert result.source.page_number is None
