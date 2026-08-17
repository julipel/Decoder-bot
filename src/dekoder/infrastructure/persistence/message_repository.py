"""
SQLAlchemy-реализация `MessageRepository` (Infrastructure Layer, задача
S2-05) поверх `MessageORM`/`mappers.py` (S2-02). Тот же стиль, что и
`SQLAlchemyUserRepository`/`SQLAlchemyConversationRepository`
(`user_repository.py`/`conversation_repository.py` в этом же пакете).

Реализует `dekoder.application.conversation.ports.MessageRepository`
структурно (Protocol) — без явного наследования. Не раскрывает
`MessageORM` наружу: каждый публичный метод возвращает доменный
`Message`/`list[Message]`/`int`, преобразование выполняют
`message_to_orm`/`message_to_domain`.

Не проверяет существование диалога и не вызывает `ConversationRepository`
— эту гарантию даёт внешний ключ `messages.conversation_id →
conversations.id` (S2-02); получение/создание `Conversation` —
ответственность вызывающего Use Case (backlog_2.md §8, «MessageRepository»,
«Ограничения»). Не решает роль сообщения, не формирует LLM-контекст, не
считает токены, не суммирует и не кэширует историю — всё это либо не
входит в Sprint 2, либо остаётся ответственностью Application Layer.

Транзакционная политика (backlog_2.md §8, «Транзакционные границы», тот
же выбор, что и у `SQLAlchemyUserRepository`/`SQLAlchemyConversationRepository`):
- `save()` делает `add()` + `flush()`, БЕЗ `commit()` — момент фиксации
  остаётся под контролем вызывающего кода (Use Case через
  `session_scope()`); предполагается сохранение НОВОГО сообщения.
  Нарушение первичного ключа (повторное сохранение с тем же `id`) или
  внешнего ключа (неизвестный `conversation_id`) не глотается молча:
  сессия откатывается, ошибка становится `InfrastructureError`;
- `history()` — только `SELECT`, не меняет состояние транзакции;
- `clear()` — одна `DELETE`-операция (`sqlalchemy.delete()`, не построчная
  загрузка и не ORM-каскад) с `flush()` БЕЗ `commit()`, по той же причине,
  что и `save()`.

Получает `AsyncSession` через конструктор — не создаёт и не закрывает
сессию сама и не передаёт её дальше в Domain Layer.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from dekoder.domain.conversation.entities import Message
from dekoder.infrastructure.persistence.mappers import message_to_domain, message_to_orm
from dekoder.infrastructure.persistence.message_orm import MessageORM
from dekoder.shared.errors import InfrastructureError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


class SQLAlchemyMessageRepository:
    """SQLAlchemy-адаптер порта `MessageRepository` поверх переданной `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, message: Message) -> Message:
        """
        Сохраняет НОВОЕ сообщение (`add()` + `flush()`, без `commit()` —
        см. докстринг модуля). Нарушение целостности (повторный `id` —
        первичный ключ, или неизвестный `conversation_id` — внешний
        ключ) не глотается молча: сессия откатывается, ошибка становится
        `InfrastructureError` (backlog_2.md §8, «нарушение уникального
        ограничения»/«нарушение ссылочной целостности» — действительно
        ошибочные состояния, а не штатное отсутствие данных).
        """
        self._session.add(message_to_orm(message))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            _logger.error("message_save_integrity_violation", error=str(exc))
            raise InfrastructureError(
                message=f"Не удалось сохранить сообщение из-за нарушения целостности: {exc}",
                user_message="Не удалось обработать запрос, попробуйте позже.",
                code="MESSAGE_SAVE_INTEGRITY_VIOLATION",
                cause=exc,
            ) from exc
        return message

    async def history(self, conversation_id: UUID) -> list[Message]:
        """
        Все сообщения диалога `conversation_id` в детерминированном
        хронологическом порядке `created_at ASC, id ASC` (backlog_2.md §7,
        «Порядок сообщений»). Пустая история — пустой список, не
        исключение. Фильтр строго по `conversation_id` — никогда не по
        владельцу диалога и не постфильтрацией в Python.
        """
        statement = (
            sa.select(MessageORM)
            .where(MessageORM.conversation_id == conversation_id)
            .order_by(MessageORM.created_at.asc(), MessageORM.id.asc())
        )
        orm_messages = (await self._session.execute(statement)).scalars().all()
        return [message_to_domain(orm_message) for orm_message in orm_messages]

    async def clear(self, conversation_id: UUID) -> int:
        """
        Удаляет все сообщения диалога `conversation_id` одной SQL
        `DELETE`-операцией (не построчная загрузка, не ORM-каскад) и
        возвращает число удалённых строк. Не трогает сам `Conversation`
        (ни саму запись, ни `closed_at`) — эта реализация вообще не знает
        о таблице `conversations`. Идемпотентна: повторный вызов на уже
        пустой истории возвращает `0`, без ошибки.
        """
        statement = sa.delete(MessageORM).where(MessageORM.conversation_id == conversation_id)
        result = cast(CursorResult, await self._session.execute(statement))
        await self._session.flush()
        return int(result.rowcount)
