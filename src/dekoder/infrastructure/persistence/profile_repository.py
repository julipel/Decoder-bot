"""
SQLAlchemy-реализация `ProfileRepository` (Infrastructure Layer, задача
S3-05, ADR-3.1) поверх `ProfileORM`/`UserActiveProfileORM`/`mappers.py`
(S3-03). Тот же стиль, что и `SQLAlchemyConversationRepository`
(задача S2-04) — `conversation_repository.py` в этом же пакете.

Реализует `dekoder.application.profile.ports.ProfileRepository`
структурно (Protocol) — без явного наследования. Не раскрывает
`ProfileORM`/`UserActiveProfileORM` наружу: каждый публичный метод
возвращает доменный `UserProfile`/`UserProfile | None`, преобразование
выполняют `profile_to_orm`/`profile_to_domain`.

`user_active_profiles` используется ТОЛЬКО здесь (ADR-3.1, «Архитектурные
заметки для Claude Code»); никакой другой код проекта не обращается к
этой таблице напрямую.

С задачи S8-06 (Sprint 8, ADR-8.7) класс дополнен методами `get_by_id`/
`create`/`update`/`archive`/`list_all` — admin CRUD каталога профилей.
Новая Alembic-миграция не потребовалась: схема `profiles` уже содержит
все поля `UserProfile` и разрешает `status = 'archived'` схемным
`CHECK`-ограничением с момента создания таблицы (S3-03). Новые методы НЕ
копируют `select_profile()`'s собственный `await self._session.commit()`
— это единичная особенность upsert-метода S3-06, не общий стиль класса;
момент фиксации решает вызывающий код через `session_scope()`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from dekoder.domain.profile.entities import UserProfile
from dekoder.domain.profile.value_objects import ProfileStatus
from dekoder.infrastructure.persistence.mappers import profile_to_domain, profile_to_orm
from dekoder.infrastructure.persistence.profile_orm import ProfileORM
from dekoder.infrastructure.persistence.user_active_profile_orm import UserActiveProfileORM
from dekoder.shared.errors import InfrastructureError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


def _now_naive_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SQLAlchemyProfileRepository:
    """SQLAlchemy-адаптер порта `ProfileRepository` поверх переданной `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[UserProfile]:
        """
        Возвращает все профили каталога со `status = 'active'`,
        отсортированные по `created_at ASC` (порядок сид-вставки,
        S3-04) — детерминированный порядок для отображения в `/profile`
        (задача S3-08), по аналогии с `MessageRepository.history()`
        (S2-05, `created_at ASC, id ASC`).
        """
        statement = (
            sa.select(ProfileORM)
            .where(ProfileORM.status == "active")
            .order_by(ProfileORM.created_at.asc(), ProfileORM.id.asc())
        )
        orm_profiles = (await self._session.execute(statement)).scalars().all()
        return [profile_to_domain(orm_profile) for orm_profile in orm_profiles]

    async def get_active_profile(self, user_id: UUID) -> UserProfile:
        """
        Один SQL-запрос: `LEFT JOIN user_active_profiles` на явно
        выбранный пользователем профиль, `COALESCE` на `id` профиля с
        `is_default=True`, если явного выбора нет (ADR-3.1) — не два
        последовательных запроса с проверкой на уровне Python.

        Технически реализовано как `LEFT JOIN` из однострочной
        производной таблицы («область видимости» одного `user_id`) на
        `user_active_profiles`, затем `JOIN` на `profiles` по
        `COALESCE(user_active_profiles.profile_id, <id профиля-дефолта>)`
        — эквивалентно прямому `LEFT JOIN ... COALESCE`, но не требует
        псевдонима для `profiles` (используется дважды: как цель
        основного JOIN и в коррелированном подзапросе дефолта).

        Отсутствие результата (пустой каталог вопреки сид-миграции
        S3-04, либо отсутствие ровно одного `is_default=True`) — не
        штатный случай (ADR-3.1, ADR-3.4 гарантируют обратное) и не
        возвращается как `None` — поднимается `InfrastructureError`, по
        аналогии с `ConversationRepository.get_active_by_user_id`,
        обрабатывающим нарушение инварианта уникальности как ошибку.
        """
        user_scope = sa.select(sa.literal(user_id, type_=sa.Uuid()).label("user_id")).subquery("user_scope")
        default_profile_id = sa.select(ProfileORM.id).where(ProfileORM.is_default.is_(True)).scalar_subquery()
        statement = (
            sa.select(ProfileORM)
            .select_from(user_scope)
            .outerjoin(UserActiveProfileORM, UserActiveProfileORM.user_id == user_scope.c.user_id)
            .join(
                ProfileORM,
                ProfileORM.id == sa.func.coalesce(UserActiveProfileORM.profile_id, default_profile_id),
            )
        )
        orm_profile = (await self._session.execute(statement)).scalar_one_or_none()
        if orm_profile is None:
            _logger.error("profile_active_not_found", user_id=str(user_id))
            raise InfrastructureError(
                message=(
                    f"Не удалось определить активный профиль пользователя {user_id}: "
                    "каталог профилей пуст или не содержит профиль с is_default=True"
                ),
                user_message="Не удалось обработать запрос, попробуйте позже.",
                code="PROFILE_ACTIVE_NOT_FOUND",
            )
        return profile_to_domain(orm_profile)

    async def select_profile(self, user_id: UUID, profile_id: UUID) -> UserProfile | None:
        """
        Сначала проверяет, что `profile_id` существует и `status =
        'active'` — если нет, возвращает `None`, ничего не записывая
        (штатный отрицательный исход, не исключение). Если найден —
        атомарный upsert `user_active_profiles` по первичному ключу
        `user_id` (`INSERT ... ON CONFLICT(user_id) DO UPDATE`, SQLite
        `sqlite.insert(...).on_conflict_do_update(...)`) — одна операция
        записи, не «сначала SELECT, потом INSERT/UPDATE» на уровне
        Python без защиты от гонки (ADR-3.1, checklist).
        """
        target_profile = await self._session.get(ProfileORM, profile_id)
        if target_profile is None or target_profile.status != "active":
            return None

        now = datetime.now(UTC).replace(tzinfo=None)
        insert_statement = sqlite_insert(UserActiveProfileORM).values(
            user_id=user_id, profile_id=profile_id, updated_at=now
        )
        upsert_statement = insert_statement.on_conflict_do_update(
            index_elements=[UserActiveProfileORM.user_id],
            set_={
                "profile_id": insert_statement.excluded.profile_id,
                "updated_at": insert_statement.excluded.updated_at,
            },
        )
        await self._session.execute(upsert_statement)
        await self._session.commit()
        return profile_to_domain(target_profile)

    async def get_by_id(self, profile_id: UUID) -> UserProfile | None:
        """Sprint 8, S8-06, ADR-8.7 — профиль по `id` независимо от `status` (в отличие от `get_active_profile`)."""
        orm_profile = await self._session.get(ProfileORM, profile_id)
        return profile_to_domain(orm_profile) if orm_profile is not None else None

    async def create(self, profile: UserProfile) -> UserProfile:
        """
        Sprint 8, S8-06, ADR-8.7 — сохраняет НОВУЮ запись профиля
        (`add()` + `flush()`, без явного `commit()` — момент фиксации
        решает вызывающий код через `session_scope()`, тот же стиль, что
        `SQLAlchemyKnowledgeDocumentRepository.save()`; НЕ копирует
        `select_profile()`'s собственный `session.commit()`).
        """
        self._session.add(profile_to_orm(profile))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            _logger.error("profile_create_integrity_violation", error=str(exc))
            raise InfrastructureError(
                message=f"Не удалось создать профиль из-за нарушения целостности: {exc}",
                user_message="Не удалось создать профиль, попробуйте позже.",
                code="PROFILE_CREATE_INTEGRITY_VIOLATION",
                cause=exc,
            ) from exc
        return profile

    async def update(self, profile: UserProfile) -> UserProfile:
        """Sprint 8, S8-06, ADR-8.7 — обновляет существующую запись профиля целиком по `profile.id`."""
        orm_profile = await self._session.get(ProfileORM, profile.id)
        if orm_profile is None:
            _logger.error("profile_update_not_found", profile_id=str(profile.id))
            raise InfrastructureError(
                message=f"Не удалось обновить профиль {profile.id}: запись не найдена в БД",
                user_message="Не удалось обновить профиль, попробуйте позже.",
                code="PROFILE_UPDATE_NOT_FOUND",
            )

        orm_profile.name = profile.name
        orm_profile.description = profile.description
        orm_profile.system_instruction = profile.system_instruction
        orm_profile.response_style = profile.response_style
        orm_profile.target_audience = profile.target_audience
        orm_profile.formality_level = profile.formality_level
        orm_profile.preferred_structure = profile.preferred_structure
        orm_profile.forbidden_phrasing = list(profile.forbidden_phrasing)
        orm_profile.preferred_model = profile.preferred_model.value if profile.preferred_model is not None else None
        orm_profile.response_length_hint = profile.response_length_hint
        orm_profile.additional_constraints = profile.additional_constraints
        orm_profile.updated_at = _now_naive_utc()
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            _logger.error("profile_update_integrity_violation", profile_id=str(profile.id), error=str(exc))
            raise InfrastructureError(
                message=f"Не удалось обновить профиль {profile.id} из-за нарушения целостности: {exc}",
                user_message="Не удалось обновить профиль, попробуйте позже.",
                code="PROFILE_UPDATE_INTEGRITY_VIOLATION",
                cause=exc,
            ) from exc
        return profile_to_domain(orm_profile)

    async def archive(self, profile_id: UUID) -> UserProfile | None:
        """Sprint 8, S8-06, ADR-8.7 — идемпотентна относительно уже `ARCHIVED`-профиля; `None` — не существует."""
        orm_profile = await self._session.get(ProfileORM, profile_id)
        if orm_profile is None:
            return None
        orm_profile.status = ProfileStatus.ARCHIVED.value
        orm_profile.updated_at = _now_naive_utc()
        await self._session.flush()
        return profile_to_domain(orm_profile)

    async def list_all(self) -> list[UserProfile]:
        """Sprint 8, S8-06, ADR-8.7 — все профили независимо от `status`, тот же порядок, что `list_active()`."""
        statement = sa.select(ProfileORM).order_by(ProfileORM.created_at.asc(), ProfileORM.id.asc())
        orm_profiles = (await self._session.execute(statement)).scalars().all()
        return [profile_to_domain(orm_profile) for orm_profile in orm_profiles]
