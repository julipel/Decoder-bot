"""
SQLAlchemy-реализация `MemoryRepository` (Infrastructure Layer, Sprint 5,
задача S5-04, ADR-5.6/ADR-5.7) поверх `MemoryRecordORM`/`mappers.py`.
Тот же стиль, что и `SQLAlchemyProfileRepository`/`SQLAlchemyMessageRepository`
(`profile_repository.py`/`message_repository.py` в этом же пакете).

Реализует `dekoder.application.memory.ports.MemoryRepository` структурно
(Protocol) — без явного наследования. Не раскрывает `MemoryRecordORM`
наружу: каждый публичный метод возвращает доменный `MemoryRecord`/
`MemoryRecord | None`/`Sequence[MemoryRecord]`, преобразование выполняют
`memory_record_to_orm`/`memory_record_to_domain`.

Транзакционная политика — как у `SQLAlchemyMessageRepository`/
`SQLAlchemyConversationRepository` (не как у `select_profile`, у которого
своя атомарная upsert-операция с собственным `commit()`): `save()`/
`update_status()`/`delete()` делают `add()`/`execute()` + `flush()`, БЕЗ
`commit()` — момент фиксации остаётся под контролем вызывающего кода
(use case через `session_scope()`).

Никакого `infrastructure/vector_storage/` — `find_relevant` реализует
простой SQL-фильтр (ADR-5.6), не векторный поиск.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import MemoryStatus
from dekoder.infrastructure.persistence.mappers import memory_record_to_domain, memory_record_to_orm
from dekoder.infrastructure.persistence.memory_record_orm import MemoryRecordORM
from dekoder.shared.errors import InfrastructureError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)

# `confidence` хранится как строка ('low'/'medium'/'high', CheckConstraint
# в MemoryRecordORM) — обычная лексикографическая сортировка ('high' <
# 'low' < 'medium') НЕ даёт "высокая значимость первой": по алфавиту
# 'medium' идёт после 'low' и 'high'. Явный CASE отображает значения в
# числовой ранг (high=3 > medium=2 > low=1), только так `ORDER BY ...
# DESC` (ADR-5.6) действительно означает «сначала самые значимые записи».
_CONFIDENCE_RANK = sa.case(
    (MemoryRecordORM.confidence == "high", 3),
    (MemoryRecordORM.confidence == "medium", 2),
    (MemoryRecordORM.confidence == "low", 1),
    else_=0,
)


def _now_naive_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SQLAlchemyMemoryRepository:
    """SQLAlchemy-адаптер порта `MemoryRepository` поверх переданной `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: MemoryRecord) -> MemoryRecord:
        """
        Сохраняет НОВУЮ запись памяти (`add()` + `flush()`, без
        `commit()` — см. докстринг модуля). Нарушение целостности
        (повторный `id` — первичный ключ, или неизвестный `user_id` —
        внешний ключ) не глотается молча: сессия откатывается, ошибка
        становится `InfrastructureError`.
        """
        self._session.add(memory_record_to_orm(record))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            _logger.error("memory_record_save_integrity_violation", error=str(exc))
            raise InfrastructureError(
                message=f"Не удалось сохранить запись памяти из-за нарушения целостности: {exc}",
                user_message="Не удалось обработать запрос, попробуйте позже.",
                code="MEMORY_RECORD_SAVE_INTEGRITY_VIOLATION",
                cause=exc,
            ) from exc
        return record

    async def find_relevant(self, user_id: UUID, limit: int) -> Sequence[MemoryRecord]:
        """
        Простой SQL-фильтр, без векторного поиска (ADR-5.6): только
        `status = 'confirmed'`, не истёкшие (`expires_at IS NULL OR
        expires_at > now`), не более `limit` записей, отсортированных по
        значимости (`confidence DESC`, через `_CONFIDENCE_RANK`), затем
        по свежести (`created_at DESC`). Единственное место, где
        применяется бизнес-правило «неподтверждённая память не входит в
        контекст» (§13.5 «Плана реализации.md»).
        """
        now = _now_naive_utc()
        statement = (
            sa.select(MemoryRecordORM)
            .where(
                MemoryRecordORM.user_id == user_id,
                MemoryRecordORM.status == MemoryStatus.CONFIRMED.value,
                sa.or_(MemoryRecordORM.expires_at.is_(None), MemoryRecordORM.expires_at > now),
            )
            .order_by(_CONFIDENCE_RANK.desc(), MemoryRecordORM.created_at.desc())
            .limit(limit)
        )
        orm_records = (await self._session.execute(statement)).scalars().all()
        return [memory_record_to_domain(orm_record) for orm_record in orm_records]

    async def list_confirmed_by_user(self, user_id: UUID) -> Sequence[MemoryRecord]:
        """
        Все подтверждённые записи пользователя, без `limit` — для `/memory`
        (задача S5-07). Порядок `created_at DESC, id ASC` — самые новые
        факты первыми, вторичная сортировка по `id` для детерминизма при
        совпадающих `created_at` (по аналогии с `MessageRepository.history`).
        """
        statement = (
            sa.select(MemoryRecordORM)
            .where(
                MemoryRecordORM.user_id == user_id,
                MemoryRecordORM.status == MemoryStatus.CONFIRMED.value,
            )
            .order_by(MemoryRecordORM.created_at.desc(), MemoryRecordORM.id.asc())
        )
        orm_records = (await self._session.execute(statement)).scalars().all()
        return [memory_record_to_domain(orm_record) for orm_record in orm_records]

    async def get_by_id(self, record_id: UUID) -> MemoryRecord | None:
        orm_record = await self._session.get(MemoryRecordORM, record_id)
        return memory_record_to_domain(orm_record) if orm_record is not None else None

    async def update_status(self, record_id: UUID, status: MemoryStatus, updated_by: str) -> MemoryRecord:
        """
        Обновляет `status`/`updated_by`/`updated_at` точечно на уже
        загруженной ORM-записи (`session.get()`, БЕЗ `session.merge()` —
        как и `SQLAlchemyConversationRepository.close()`, чтобы не
        перезаписать остальные колонки случайно устаревшей копией).
        Запись должна существовать — вызывающий use case
        (`ConfirmMemoryRecord`/`RejectMemoryRecord`) уже прочитал её через
        `get_by_id`; отсутствие здесь — рассогласование, не штатный
        случай, поэтому `InfrastructureError`, а не тихий `None`.
        """
        orm_record = await self._session.get(MemoryRecordORM, record_id)
        if orm_record is None:
            _logger.error("memory_record_update_status_not_found", record_id=str(record_id))
            raise InfrastructureError(
                message=f"Не удалось обновить статус записи памяти {record_id}: запись не найдена в БД",
                user_message="Не удалось обработать запрос, попробуйте позже.",
                code="MEMORY_RECORD_UPDATE_STATUS_NOT_FOUND",
            )

        orm_record.status = status.value
        orm_record.updated_by = updated_by
        orm_record.updated_at = _now_naive_utc()
        await self._session.flush()
        return memory_record_to_domain(orm_record)

    async def delete(self, record_id: UUID, user_id: UUID) -> None:
        """
        Удаляет запись одной SQL `DELETE`-операцией, ограниченной ОБОИМИ
        `id` И `user_id` (ADR-5.10: пользователь не может удалить чужую
        запись, проверяется здесь, не только на уровне Telegram-хендлера).
        Идемпотентна: несуществующая запись или запись другого
        пользователя — 0 удалённых строк, не ошибка.
        """
        statement = sa.delete(MemoryRecordORM).where(
            MemoryRecordORM.id == record_id, MemoryRecordORM.user_id == user_id
        )
        await self._session.execute(statement)
        await self._session.flush()
