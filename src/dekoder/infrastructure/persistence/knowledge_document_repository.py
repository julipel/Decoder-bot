"""
SQLAlchemy-реализация `KnowledgeDocumentRepository` (Infrastructure Layer,
Sprint 6, задача S6-04, ADR-6.1/6.2/6.9) поверх `KnowledgeDocumentORM`/
`mappers.py`. Тот же стиль, что и `SQLAlchemyMemoryRepository`.

Не открывается наружу через `ConversationRepositories` — используется
собственной, отдельной от диалоговой фабрикой репозиториев
(`bootstrap/repositories.py::build_knowledge_repositories_factory`,
задача S6-06), т.к. база знаний не участвует в транзакции
`ProcessUserMessage` (ADR-6.4).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from dekoder.domain.knowledge.entities import KnowledgeDocument
from dekoder.infrastructure.persistence.knowledge_document_orm import KnowledgeDocumentORM
from dekoder.infrastructure.persistence.mappers import knowledge_document_to_domain, knowledge_document_to_orm
from dekoder.shared.errors import InfrastructureError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


def _now_naive_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SQLAlchemyKnowledgeDocumentRepository:
    """SQLAlchemy-адаптер порта `KnowledgeDocumentRepository` поверх переданной `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, document: KnowledgeDocument) -> KnowledgeDocument:
        """Сохраняет НОВУЮ запись (`add()` + `flush()`, без `commit()` — момент фиксации решает вызывающий код)."""
        self._session.add(knowledge_document_to_orm(document))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            _logger.error("knowledge_document_save_integrity_violation", error=str(exc))
            raise InfrastructureError(
                message=f"Не удалось сохранить документ базы знаний из-за нарушения целостности: {exc}",
                user_message="Не удалось обработать документ, попробуйте позже.",
                code="KNOWLEDGE_DOCUMENT_SAVE_INTEGRITY_VIOLATION",
                cause=exc,
            ) from exc
        return document

    async def get_by_id(self, document_id: UUID) -> KnowledgeDocument | None:
        orm_document = await self._session.get(KnowledgeDocumentORM, document_id)
        return knowledge_document_to_domain(orm_document) if orm_document is not None else None

    async def get_by_checksum(self, checksum: str) -> KnowledgeDocument | None:
        statement = sa.select(KnowledgeDocumentORM).where(KnowledgeDocumentORM.checksum == checksum)
        orm_document = (await self._session.execute(statement)).scalar_one_or_none()
        return knowledge_document_to_domain(orm_document) if orm_document is not None else None

    async def update(self, document: KnowledgeDocument) -> KnowledgeDocument:
        """
        Обновляет существующую запись целиком на уже загруженной ORM-
        записи (`session.get()`, БЕЗ `session.merge()` — как и
        `SQLAlchemyMemoryRepository.update_status`). Запись должна
        существовать — вызывающий код (`IndexKnowledgeDocumentUseCase`)
        уже прочитал или только что сохранил её.
        """
        orm_document = await self._session.get(KnowledgeDocumentORM, document.id)
        if orm_document is None:
            _logger.error("knowledge_document_update_not_found", document_id=str(document.id))
            raise InfrastructureError(
                message=f"Не удалось обновить документ базы знаний {document.id}: запись не найдена в БД",
                user_message="Не удалось обработать документ, попробуйте позже.",
                code="KNOWLEDGE_DOCUMENT_UPDATE_NOT_FOUND",
            )

        orm_document.title = document.title
        orm_document.status = document.status.value
        orm_document.tags = list(document.tags)
        orm_document.description = document.description
        orm_document.chunk_count = document.chunk_count
        orm_document.error_message = document.error_message
        orm_document.updated_at = _now_naive_utc()
        indexed_at = document.indexed_at
        orm_document.indexed_at = indexed_at.astimezone(UTC).replace(tzinfo=None) if indexed_at is not None else None
        await self._session.flush()
        return knowledge_document_to_domain(orm_document)

    async def delete(self, document_id: UUID) -> None:
        """Удаляет запись одной SQL `DELETE`-операцией. Идемпотентна: несуществующая запись — 0 удалённых строк."""
        statement = sa.delete(KnowledgeDocumentORM).where(KnowledgeDocumentORM.id == document_id)
        await self._session.execute(statement)
        await self._session.flush()
