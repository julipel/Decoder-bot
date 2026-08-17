"""
`SemanticSearchService` — реализация `KnowledgeSearchService` (Sprint 6,
задача S6-07, ADR-6.4, §14.7 «Плана реализации.md»).

Композиция `EmbeddingProvider` + `VectorRepository` за параметрами по
умолчанию из `KnowledgeSettings` (`limit`/`min_relevance_score`) — тот же
уровень абстракции, что и `DeterministicPromptBuilder` (композиция
`PromptTemplateRepository` + `TokenBudgetPolicy`). Не use case с
Command/Result DTO (как `CreateMemoryRecordUseCase`) — единственный
вызывающий, `ProcessUserMessage`, не нуждается в фильтрах по документам/
тегам (это административный сценарий, не в Sprint 6, ADR-6.6); отдельный
"SearchKnowledgeUseCase" с этими фильтрами не создаётся заранее — когда он
понадобится Этапу 10, он вызовет `VectorRepository.search(...)` напрямую,
она уже их поддерживает.

Пустой результат (нет фрагментов выше порога релевантности) — штатный
исход (§14.7), не отличается от отсутствия базы знаний вовсе.
"""

from __future__ import annotations

from collections.abc import Sequence

from dekoder.application.knowledge.ports import EmbeddingProvider, VectorRepository
from dekoder.domain.knowledge.search import SearchResult


class SemanticSearchService:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_repository: VectorRepository,
        limit: int,
        min_relevance_score: float,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._vector_repository = vector_repository
        self._limit = limit
        self._min_relevance_score = min_relevance_score

    async def search(self, query_text: str) -> Sequence[SearchResult]:
        vectors = await self._embedding_provider.embed_batch([query_text])
        query_vector = vectors[0]
        return await self._vector_repository.search(
            query_vector,
            limit=self._limit,
            min_score=self._min_relevance_score,
        )
