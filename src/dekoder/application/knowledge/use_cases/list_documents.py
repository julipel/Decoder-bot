"""
`ListKnowledgeDocumentsUseCase` — тонкая обёртка над `KnowledgeDocumentRepository.list_all()`
(Sprint 8, задача S8-04, ADR-8.5).

Вызывающий код — внешний driving-адаптер (REST-роут `GET
/admin/documents`, CLI `scripts/index_document.py list`), не
`ProcessUserMessage` — тот же прецедент, что и тонкие read-use-case'ы
`ListProfiles`/`GetActiveProfile` (`application/profile/use_cases/`),
вызываемые Telegram-хендлером, не `ProcessUserMessage`.
"""

from __future__ import annotations

from collections.abc import Sequence

from dekoder.application.knowledge.ports import KnowledgeDocumentRepository
from dekoder.domain.knowledge.entities import KnowledgeDocument


class ListKnowledgeDocumentsUseCase:
    def __init__(self, document_repository: KnowledgeDocumentRepository) -> None:
        self._document_repository = document_repository

    async def execute(self) -> Sequence[KnowledgeDocument]:
        return await self._document_repository.list_all()
