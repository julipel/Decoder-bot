"""Тесты `SemanticSearchService` (Sprint 6, задача S6-07, ADR-6.4/§14.7)."""

from __future__ import annotations

from uuid import uuid4

from tests.support.fake_knowledge_repositories import FakeEmbeddingProvider, FakeVectorRepository

from dekoder.application.knowledge.services.semantic_search_service import SemanticSearchService
from dekoder.domain.knowledge.search import SearchResult, SourceReference


def _make_result() -> SearchResult:
    return SearchResult(
        text="Найденный фрагмент.",
        score=0.87,
        source=SourceReference(
            document_id=uuid4(), document_title="Документ", chunk_index=0, section_title=None, page_number=None
        ),
    )


class TestSemanticSearchService:
    async def test_embeds_query_and_returns_vector_repository_results(self) -> None:
        expected = [_make_result()]
        embedding_provider = FakeEmbeddingProvider(vector_size=4)
        vector_repository = FakeVectorRepository(search_results=expected)
        service = SemanticSearchService(
            embedding_provider=embedding_provider,
            vector_repository=vector_repository,
            limit=5,
            min_relevance_score=0.5,
        )

        results = await service.search("Как это работает?")

        assert results == expected
        assert embedding_provider.embed_calls == [["Как это работает?"]]
        assert len(vector_repository.search_calls) == 1
        call = vector_repository.search_calls[0]
        assert call["limit"] == 5
        assert call["min_score"] == 0.5
        assert call["query_vector"] == [0.0, 0.0, 0.0, 0.0]

    async def test_empty_search_result_is_returned_as_is(self) -> None:
        embedding_provider = FakeEmbeddingProvider()
        vector_repository = FakeVectorRepository(search_results=[])
        service = SemanticSearchService(
            embedding_provider=embedding_provider, vector_repository=vector_repository, limit=5, min_relevance_score=0.5
        )

        results = await service.search("Ничего не найдётся")

        assert results == []
