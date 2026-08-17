"""
SQLAlchemy-реализация `ModelSelectionRepository` (Infrastructure Layer,
Sprint 7, задача S7-04, ADR-7.5) поверх `UserActiveModelORM`. Прямой
прецедент — `SQLAlchemyProfileRepository.select_profile`/
`user_active_profiles` (`profile_repository.py`, ADR-3.1): та же
атомарная upsert-операция по первичному ключу `user_id`, с собственным
`commit()` (не «сначала SELECT, потом INSERT/UPDATE» на уровне Python
без защиты от гонки).

Реализует `dekoder.application.model_catalog.ports.ModelSelectionRepository`
структурно (Protocol) — без явного наследования.

`user_active_models` используется ТОЛЬКО здесь (по аналогии с
`user_active_profiles`, ADR-3.1 «Архитектурные заметки для Claude Code»);
никакой другой код проекта не обращается к этой таблице напрямую.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.infrastructure.persistence.user_active_model_orm import UserActiveModelORM


class SQLAlchemyModelSelectionRepository:
    """SQLAlchemy-адаптер порта `ModelSelectionRepository` поверх переданной `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_selected(self, user_id: UUID) -> ModelId | None:
        """Возвращает `model_id` персонального выбора пользователя или `None`, если выбор ещё не сделан."""
        orm_selection = await self._session.get(UserActiveModelORM, user_id)
        return ModelId(orm_selection.model_id) if orm_selection is not None else None

    async def select(self, user_id: UUID, model_id: ModelId) -> None:
        """
        Атомарный upsert `user_active_models` по первичному ключу
        `user_id` (`INSERT ... ON CONFLICT(user_id) DO UPDATE`, SQLite
        `sqlite.insert(...).on_conflict_do_update(...)`) — одна операция
        записи, тем же приёмом, что `SQLAlchemyProfileRepository.
        select_profile` (ADR-3.1, ADR-7.5 checklist).
        """
        now = datetime.now(UTC).replace(tzinfo=None)
        insert_statement = sqlite_insert(UserActiveModelORM).values(
            user_id=user_id, model_id=model_id.value, selected_at=now
        )
        upsert_statement = insert_statement.on_conflict_do_update(
            index_elements=[UserActiveModelORM.user_id],
            set_={
                "model_id": insert_statement.excluded.model_id,
                "selected_at": insert_statement.excluded.selected_at,
            },
        )
        await self._session.execute(upsert_statement)
        await self._session.commit()
