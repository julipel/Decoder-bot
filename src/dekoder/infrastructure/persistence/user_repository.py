"""
SQLAlchemy-реализация `UserRepository` (Infrastructure Layer, задача
S2-03) поверх `UserORM`/`mappers.py` (S2-02).

Реализует `dekoder.application.user.ports.UserRepository` структурно
(Protocol) — без явного наследования, как и `OpenRouterLLMAdapter`
реализует `LLMProvider`. Не раскрывает `UserORM` наружу: каждый публичный
метод возвращает доменный `User | None`/`User`, преобразование выполняют
`user_to_orm`/`user_to_domain`.

Не занимается диалогами и сообщениями (`ConversationRepository`/
`MessageRepository` — следующие задачи Sprint 2, backlog_2.md §8).

Транзакционная политика (backlog_2.md §8, «Транзакционные границы»):
- `get_by_id`/`get_by_telegram_user_id` — только `SELECT`, не меняют
  состояние транзакции;
- `save()` делает `add()` + `flush()`, БЕЗ `commit()` — момент фиксации
  транзакции остаётся под контролем вызывающего кода (будущего Use Case
  через `session_scope()`, `infrastructure/persistence/session.py`);
  предполагается сохранение НОВОЙ сущности (см. докстринг порта);
- `get_or_create_by_telegram_user_id()` — единственное исключение:
  самостоятельная короткая транзакция с `commit()`/`rollback()` внутри,
  так как это автономная атомарная операция без сетевых вызовов
  (backlog_2.md §8 явно это допускает). Транзакция не остаётся открытой
  во время какого-либо сетевого вызова — в этом методе таких вызовов нет.

Получает `AsyncSession` через конструктор — не создаёт и не закрывает
сессию сама и не передаёт её дальше в Domain Layer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from dekoder.domain.user.entities import User
from dekoder.infrastructure.persistence.mappers import user_to_domain, user_to_orm
from dekoder.infrastructure.persistence.user_orm import UserORM
from dekoder.shared.errors import InfrastructureError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)

# Подстрока, по которой распознаётся нарушение именно уникального
# ограничения `uq_users_telegram_user_id` (user_orm.py) в тексте ошибки
# SQLite. SQLite не включает имя constraint'а в `exc.orig` — только имя
# таблицы и колонки: `UNIQUE constraint failed: users.telegram_user_id`.
# Sprint 2 использует только SQLite (backlog_2.md §3), поэтому другой
# диалект здесь не учитывается.
_TELEGRAM_USER_ID_UNIQUE_VIOLATION_MARKER = "users.telegram_user_id"


class SQLAlchemyUserRepository:
    """SQLAlchemy-адаптер порта `UserRepository` поверх переданной `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        orm_user = await self._session.get(UserORM, user_id)
        return user_to_domain(orm_user) if orm_user is not None else None

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> User | None:
        statement = sa.select(UserORM).where(UserORM.telegram_user_id == telegram_user_id)
        orm_user = (await self._session.execute(statement)).scalar_one_or_none()
        return user_to_domain(orm_user) if orm_user is not None else None

    async def save(self, user: User) -> User:
        """
        Сохраняет НОВОГО пользователя (`add()` + `flush()`, без
        `commit()` — см. докстринг модуля). Нарушение целостности (в
        первую очередь — повторный `telegram_user_id`) не глотается
        молча: сессия откатывается, ошибка становится
        `InfrastructureError` (backlog_2.md §8, «нарушение уникального
        ограничения» — один из примеров действительно ошибочного
        состояния, а не штатного отсутствия данных).
        """
        self._session.add(user_to_orm(user))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            _logger.error("user_save_integrity_violation", error=str(exc))
            raise InfrastructureError(
                message=f"Не удалось сохранить пользователя из-за нарушения целостности: {exc}",
                user_message="Не удалось обработать запрос, попробуйте позже.",
                code="USER_SAVE_INTEGRITY_VIOLATION",
                cause=exc,
            ) from exc
        return user

    async def get_or_create_by_telegram_user_id(self, telegram_user_id: int) -> User:
        """
        Идемпотентная get-or-create. Алгоритм (backlog_2.md §8,
        «Конкурентный доступ»):

        1. найти пользователя по `telegram_user_id` — если найден, вернуть;
        2. иначе создать новую доменную сущность `User` и сохранить с
           `commit()` (самостоятельная короткая транзакция, см. докстринг
           модуля);
        3. при конфликте уникальности (`IntegrityError`, гонка двух
           параллельных вызовов с одним и тем же `telegram_user_id`) —
           откатить транзакцию и заново найти пользователя по
           `telegram_user_id`;
        4. если после отката пользователь всё же не находится —
           `IntegrityError` не был гонкой уникальности `telegram_user_id`
           (или запись исчезла по другой причине) — пробросить как
           `InfrastructureError`, не глотать молча.

        Единственный источник истины против дублей — уникальное
        ограничение БД `uq_users_telegram_user_id` (задача S2-02), не
        проверка «сначала SELECT, затем INSERT» на уровне Python.
        """
        existing = await self.get_by_telegram_user_id(telegram_user_id)
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        new_user = User(id=uuid4(), telegram_user_id=telegram_user_id, created_at=now, updated_at=now)
        self._session.add(user_to_orm(new_user))
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            if not self._is_telegram_user_id_conflict(exc):
                _logger.error("user_get_or_create_unexpected_integrity_error", error=str(exc))
                raise InfrastructureError(
                    message=f"Не удалось создать пользователя из-за нарушения целостности: {exc}",
                    user_message="Не удалось обработать запрос, попробуйте позже.",
                    code="USER_CREATE_INTEGRITY_VIOLATION",
                    cause=exc,
                ) from exc

            _logger.info("user_get_or_create_race_detected", telegram_user_id=telegram_user_id)
            existing_after_conflict = await self.get_by_telegram_user_id(telegram_user_id)
            if existing_after_conflict is None:
                _logger.error(
                    "user_get_or_create_conflict_unresolved",
                    telegram_user_id=telegram_user_id,
                )
                raise InfrastructureError(
                    message=(
                        "Нарушение уникальности telegram_user_id при создании пользователя, "
                        "но повторный поиск после rollback не нашёл запись"
                    ),
                    user_message="Не удалось обработать запрос, попробуйте позже.",
                    code="USER_CONFLICT_UNRESOLVED",
                    cause=exc,
                ) from exc
            return existing_after_conflict

        return new_user

    @staticmethod
    def _is_telegram_user_id_conflict(exc: IntegrityError) -> bool:
        """
        Отличает нарушение именно `uq_users_telegram_user_id` от прочих
        `IntegrityError` (backlog_2.md §8: «не считать любой
        IntegrityError доказательством гонки»).
        """
        return _TELEGRAM_USER_ID_UNIQUE_VIOLATION_MARKER in str(exc.orig)
