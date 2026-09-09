"""
SQLAlchemy-реализация `WebSearchSettingRepository` (Infrastructure Layer,
внеспринтовая задача 2026-09-09) поверх `UserWebSearchSettingORM`. Прямой
прецедент — `SQLAlchemyModelSelectionRepository.select`/
`user_active_models` (ADR-7.5): та же атомарная upsert-операция по
первичному ключу `user_id`, с собственным `commit()`.

Реализует `dekoder.application.conversation.ports.WebSearchSettingRepository`
структурно (Protocol) — без явного наследования.

`user_web_search_settings` используется ТОЛЬКО здесь (по аналогии с
`user_active_models`); никакой другой код проекта не обращается к этой
таблице напрямую.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from dekoder.infrastructure.persistence.user_web_search_setting_orm import UserWebSearchSettingORM


class SQLAlchemyWebSearchSettingRepository:
    """SQLAlchemy-адаптер порта `WebSearchSettingRepository` поверх переданной `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_enabled(self, user_id: UUID) -> bool:
        """Возвращает `True`, если пользователь включил веб-поиск; отсутствие записи — штатное «выключено»."""
        orm_setting = await self._session.get(UserWebSearchSettingORM, user_id)
        return orm_setting.enabled if orm_setting is not None else False

    async def set_enabled(self, user_id: UUID, enabled: bool) -> None:
        """
        Атомарный upsert `user_web_search_settings` по первичному ключу
        `user_id` (`INSERT ... ON CONFLICT(user_id) DO UPDATE`) — тем же
        приёмом, что `SQLAlchemyModelSelectionRepository.select` (ADR-7.5).
        """
        now = datetime.now(UTC).replace(tzinfo=None)
        insert_statement = sqlite_insert(UserWebSearchSettingORM).values(
            user_id=user_id, enabled=enabled, updated_at=now
        )
        upsert_statement = insert_statement.on_conflict_do_update(
            index_elements=[UserWebSearchSettingORM.user_id],
            set_={
                "enabled": insert_statement.excluded.enabled,
                "updated_at": insert_statement.excluded.updated_at,
            },
        )
        await self._session.execute(upsert_statement)
        await self._session.commit()
