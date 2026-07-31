"""
SQLAlchemy-реализация `ConversationRepository` (Infrastructure Layer,
задача S2-04) поверх `ConversationORM`/`mappers.py` (S2-02). Тот же
стиль, что и `SQLAlchemyUserRepository` (задача S2-03) —
`user_repository.py` в этом же пакете.

Реализует `dekoder.application.conversation.ports.ConversationRepository`
структурно (Protocol) — без явного наследования. Не раскрывает
`ConversationORM` наружу: каждый публичный метод возвращает доменный
`Conversation | None`/`Conversation`, преобразование выполняют
`conversation_to_orm`/`conversation_to_domain`.

Не занимается сообщениями (`MessageRepository` — следующая задача Sprint 2,
backlog_2.md §8) и не проверяет существование пользователя — эту
гарантию даёт внешний ключ `conversations.user_id → users.id` (S2-02);
получение/создание `User` — ответственность вызывающего Use Case, не
этого репозитория (backlog_2.md §8, «ConversationRepository»,
«Ограничения»).

Транзакционная политика (backlog_2.md §8, «Транзакционные границы»,
тот же выбор, что и у `SQLAlchemyUserRepository`):
- `get_by_id`/`get_active_by_user_id` — только `SELECT`, не меняют
  состояние транзакции;
- `save()` делает `add()` + `flush()`, БЕЗ `commit()` — момент фиксации
  остаётся под контролем вызывающего кода (Use Case через
  `session_scope()`); предполагается сохранение НОВОЙ сущности;
- `close()` обновляет только `closed_at`/`updated_at` конкретной ORM-
  записи (получена через `session.get()`, БЕЗ `session.merge()` — чтобы
  случайно не перезаписать `user_id`/`created_at` значениями из
  переданной доменной сущности) и делает `flush()`, БЕЗ `commit()` — по
  той же причине, что и `save()`;
- `get_or_create_active()` — как и `get_or_create_by_telegram_user_id`
  у `UserRepository`: единственное исключение с собственным
  `commit()`/`rollback()` внутри (автономная атомарная операция без
  сетевых вызовов, backlog_2.md §8 это прямо допускает).

Получает `AsyncSession` через конструктор — не создаёт и не закрывает
сессию сама и не передаёт её дальше в Domain Layer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSession

from dekoder.domain.conversation.entities import Conversation
from dekoder.infrastructure.persistence.conversation_orm import ConversationORM
from dekoder.infrastructure.persistence.mappers import conversation_to_domain, conversation_to_orm
from dekoder.shared.errors import InfrastructureError, ValidationError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)

# Подстрока, по которой распознаётся нарушение именно частичного
# уникального индекса `uq_conversations_active_user` (conversation_orm.py)
# в тексте ошибки SQLite. SQLite не включает имя constraint'а/индекса в
# `exc.orig` для UNIQUE-нарушений — только имя таблицы и колонки:
# `UNIQUE constraint failed: conversations.user_id`. Обычный (не
# уникальный) `ix_conversations_user_id` не может вызвать `IntegrityError`,
# поэтому эта подстрока однозначно указывает на нарушение именно
# `uq_conversations_active_user`. Проверено вручную при реализации задачи.
# Sprint 2 использует только SQLite (backlog_2.md §3), поэтому другой
# диалект здесь не учитывается.
_ACTIVE_CONVERSATION_UNIQUE_VIOLATION_MARKER = "conversations.user_id"


class SQLAlchemyConversationRepository:
    """SQLAlchemy-адаптер порта `ConversationRepository` поверх переданной `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        orm_conversation = await self._session.get(ConversationORM, conversation_id)
        return conversation_to_domain(orm_conversation) if orm_conversation is not None else None

    async def get_active_by_user_id(self, user_id: UUID) -> Conversation | None:
        """
        Активность — строго `closed_at IS NULL` (никакого отдельного
        статуса). `scalar_one_or_none()` — намеренно, не `.first()`: если
        в БД вопреки `uq_conversations_active_user` окажется больше
        одного активного диалога, это нарушение инварианта (backlog_2.md
        §15, инвариант 5), и метод должен упасть (`MultipleResultsFound`),
        а не молча выбрать первую строку.
        """
        statement = sa.select(ConversationORM).where(
            ConversationORM.user_id == user_id, ConversationORM.closed_at.is_(None)
        )
        try:
            orm_conversation = (await self._session.execute(statement)).scalar_one_or_none()
        except MultipleResultsFound as exc:
            _logger.error("conversation_multiple_active_found", user_id=str(user_id))
            raise InfrastructureError(
                message=(
                    f"У пользователя {user_id} найдено более одного активного диалога — "
                    "нарушение инварианта уникальности на уровне БД"
                ),
                user_message="Не удалось обработать запрос, попробуйте позже.",
                code="CONVERSATION_MULTIPLE_ACTIVE_FOUND",
                cause=exc,
            ) from exc
        return conversation_to_domain(orm_conversation) if orm_conversation is not None else None

    async def save(self, conversation: Conversation) -> Conversation:
        """
        Сохраняет НОВЫЙ диалог (`add()` + `flush()`, без `commit()` — см.
        докстринг модуля). Нарушение целостности (в первую очередь —
        второй активный диалог того же пользователя,
        `uq_conversations_active_user`) не глотается молча: сессия
        откатывается, ошибка становится `InfrastructureError`
        (backlog_2.md §8, «нарушение уникального ограничения» —
        действительно ошибочное состояние, а не штатное отсутствие
        данных).
        """
        self._session.add(conversation_to_orm(conversation))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            _logger.error("conversation_save_integrity_violation", error=str(exc))
            raise InfrastructureError(
                message=f"Не удалось сохранить диалог из-за нарушения целостности: {exc}",
                user_message="Не удалось обработать запрос, попробуйте позже.",
                code="CONVERSATION_SAVE_INTEGRITY_VIOLATION",
                cause=exc,
            ) from exc
        return conversation

    async def close(self, conversation: Conversation) -> Conversation:
        """
        Обновляет `closed_at`/`updated_at` конкретной ORM-записи по
        `conversation.id`. Ожидает сущность, уже закрытую доменным
        методом `Conversation.close(...)` — проверка доменных
        инвариантов (повторное закрытие, `closed_at` раньше `created_at`)
        выполняется в Domain Layer, не здесь; если вызвать `close()` с
        ещё активной сущностью (`closed_at is None`), это ошибка вызова
        контракта — `ValidationError`, не тихая запись `NULL` поверх
        существующего `closed_at`.

        Запись получается через `session.get()` и обновляется точечно
        (`orm_conversation.closed_at = ...`), БЕЗ `session.merge()`:
        `merge()` переписал бы все колонки значениями из переданной
        доменной сущности, что случайно могло бы перезаписать
        `user_id`/`created_at`, если вызывающий код передаст неполную
        или устаревшую копию сущности. Диалог не удаляется, сообщения не
        затрагиваются — эта реализация вообще не знает о таблице
        `messages`.

        Отсутствие записи с данным `id` в БД (в отличие от
        `get_by_id`/`get_active_by_user_id`, где отсутствие — нормальное
        состояние) здесь означает рассогласование: вызывающий код уже
        должен был получить эту сущность через `get_by_id`/
        `get_active_by_user_id`/`get_or_create_active` — трактуется как
        `InfrastructureError`, не как `None`.
        """
        if conversation.closed_at is None:
            raise ValidationError(
                message=(
                    f"close() ожидает диалог {conversation.id}, уже закрытый доменным методом "
                    "Conversation.close(...) (closed_at is None)"
                ),
                user_message="Не удалось обработать запрос, попробуйте позже.",
                code="CONVERSATION_CLOSE_REQUIRES_CLOSED_ENTITY",
            )

        orm_conversation = await self._session.get(ConversationORM, conversation.id)
        if orm_conversation is None:
            _logger.error("conversation_close_not_found", conversation_id=str(conversation.id))
            raise InfrastructureError(
                message=f"Не удалось закрыть диалог {conversation.id}: запись не найдена в БД",
                user_message="Не удалось обработать запрос, попробуйте позже.",
                code="CONVERSATION_CLOSE_NOT_FOUND",
            )

        closed_snapshot = conversation_to_orm(conversation)
        orm_conversation.closed_at = closed_snapshot.closed_at
        orm_conversation.updated_at = closed_snapshot.updated_at
        await self._session.flush()
        return conversation

    async def get_or_create_active(self, user_id: UUID) -> Conversation:
        """
        Идемпотентная get-or-create. Алгоритм (backlog_2.md §8,
        «Конкурентный доступ», по аналогии с `SQLAlchemyUserRepository.
        get_or_create_by_telegram_user_id`):

        1. найти активный диалог пользователя — если найден, вернуть;
        2. иначе создать новую доменную сущность `Conversation`
           (`closed_at=None`) и сохранить с `commit()` (самостоятельная
           короткая транзакция, см. докстринг модуля);
        3. при конфликте уникальности (`IntegrityError`, гонка двух
           параллельных вызовов для одного и того же `user_id`) —
           откатить транзакцию и заново найти активный диалог;
        4. если после отката активный диалог всё же не находится —
           `IntegrityError` не был гонкой уникальности активного диалога
           (или запись исчезла по другой причине) — пробросить как
           `InfrastructureError`, не глотать молча.

        Единственный источник истины против дублей — уникальное
        ограничение БД `uq_conversations_active_user` (задача S2-02), не
        проверка «сначала SELECT, затем INSERT» на уровне Python.
        """
        existing = await self.get_active_by_user_id(user_id)
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        new_conversation = Conversation(id=uuid4(), user_id=user_id, created_at=now, updated_at=now, closed_at=None)
        self._session.add(conversation_to_orm(new_conversation))
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            if not self._is_active_conversation_conflict(exc):
                _logger.error("conversation_get_or_create_unexpected_integrity_error", error=str(exc))
                raise InfrastructureError(
                    message=f"Не удалось создать диалог из-за нарушения целостности: {exc}",
                    user_message="Не удалось обработать запрос, попробуйте позже.",
                    code="CONVERSATION_CREATE_INTEGRITY_VIOLATION",
                    cause=exc,
                ) from exc

            _logger.info("conversation_get_or_create_race_detected", user_id=str(user_id))
            existing_after_conflict = await self.get_active_by_user_id(user_id)
            if existing_after_conflict is None:
                _logger.error("conversation_get_or_create_conflict_unresolved", user_id=str(user_id))
                raise InfrastructureError(
                    message=(
                        "Нарушение уникальности активного диалога при создании, "
                        "но повторный поиск после rollback не нашёл запись"
                    ),
                    user_message="Не удалось обработать запрос, попробуйте позже.",
                    code="CONVERSATION_CONFLICT_UNRESOLVED",
                    cause=exc,
                ) from exc
            return existing_after_conflict

        return new_conversation

    @staticmethod
    def _is_active_conversation_conflict(exc: IntegrityError) -> bool:
        """
        Отличает нарушение именно `uq_conversations_active_user` от
        прочих `IntegrityError` (backlog_2.md §8: «не считать любой
        IntegrityError доказательством гонки»).
        """
        return _ACTIVE_CONVERSATION_UNIQUE_VIOLATION_MARKER in str(exc.orig)
