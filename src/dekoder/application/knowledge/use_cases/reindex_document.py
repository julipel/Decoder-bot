"""
`ReindexKnowledgeDocumentUseCase` — тонкая обёртка над `DocumentStorage.read()`
+ `IndexKnowledgeDocumentUseCase` (Sprint 8, задача S8-04, ADR-8.6) —
повторная индексация уже загруженного документа без повторной загрузки
файла администратором.

НЕ дублирует 12-шаговый конвейер `IndexKnowledgeDocumentUseCase` — читает
уже сохранённые байты через `DocumentStorage.read(document_id)` (порт
существует с Sprint 6) и делегирует весь конвейер уже существующему use
case'у. Работает благодаря checksum-дедупликации (ADR-6.9):
`IndexKnowledgeDocumentUseCase` пересчитает тот же checksum (контент не
изменился), найдёт существующую запись через `get_by_checksum`,
переиспользует её `id`, перезапустит статус `INDEXING -> INDEXED/FAILED/
UNSUPPORTED`, удалит и заново запишет векторы.

`None` — штатный отрицательный исход (`document_id` не существует), не
исключение; REST-роут транслирует `None` в `NotFoundError`/404 (ADR-8.12,
ADR-8.6: reindex несуществующего документа — содержательная ошибка
клиента, не идемпотентный no-op, в отличие от `DELETE`).
"""

from __future__ import annotations

from uuid import UUID

from dekoder.application.knowledge.dto import IndexDocumentCommand, IndexDocumentResult
from dekoder.application.knowledge.ports import DocumentStorage, KnowledgeDocumentRepository
from dekoder.application.knowledge.use_cases.index_document import IndexKnowledgeDocumentUseCase
from dekoder.shared.logging import get_logger, log_audit_event

_logger = get_logger(__name__)


class ReindexKnowledgeDocumentUseCase:
    def __init__(
        self,
        document_repository: KnowledgeDocumentRepository,
        document_storage: DocumentStorage,
        index_use_case: IndexKnowledgeDocumentUseCase,
    ) -> None:
        self._document_repository = document_repository
        self._document_storage = document_storage
        self._index_use_case = index_use_case

    async def execute(self, document_id: UUID) -> IndexDocumentResult | None:
        document = await self._document_repository.get_by_id(document_id)
        if document is None:
            return None

        content = await self._document_storage.read(document_id)
        log_audit_event(_logger, "knowledge_document_reindex_requested", document_id=str(document_id))
        command = IndexDocumentCommand(
            title=document.title,
            source_filename=document.source_filename,
            content=content,
            tags=document.tags,
            description=document.description,
        )
        return await self._index_use_case.execute(command)
