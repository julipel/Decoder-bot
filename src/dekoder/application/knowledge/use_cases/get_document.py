"""
`GetKnowledgeDocumentUseCase` — тонкая обёртка над `KnowledgeDocumentRepository.get_by_id()`
(Sprint 8, задача S8-04, ADR-8.5) — статус/детали одного документа для
admin-обзора (`GET /admin/documents/{id}`).

`None` — штатный отрицательный исход (документ не существует), не
исключение; REST-роут транслирует `None` в `NotFoundError`/404
(ADR-8.12) — use case сам `NotFoundError` не поднимает.
"""

from __future__ import annotations

from uuid import UUID

from dekoder.application.knowledge.ports import KnowledgeDocumentRepository
from dekoder.domain.knowledge.entities import KnowledgeDocument


class GetKnowledgeDocumentUseCase:
    def __init__(self, document_repository: KnowledgeDocumentRepository) -> None:
        self._document_repository = document_repository

    async def execute(self, document_id: UUID) -> KnowledgeDocument | None:
        return await self._document_repository.get_by_id(document_id)
