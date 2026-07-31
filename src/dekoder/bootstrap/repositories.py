"""
Bootstrap-фабрики репозиториев (Sprint 2, задачи S2-03/S2-04).

Единственное место, которому разрешено знать одновременно про порты
`UserRepository`/`ConversationRepository` (`application/user/ports.py`,
`application/conversation/ports.py`) и их конкретные SQLAlchemy-
реализации (`infrastructure/persistence/{user_repository.py,
conversation_repository.py}`) — то же правило единственной точки сборки,
что и у `bootstrap/container.py` для `LLMProvider` (claude.md §8.5, §29).

Задачи S2-03/S2-04 намеренно НЕ подключают эти фабрики ни в
`ApplicationContainer`, ни в `ProcessUserMessage` — расширение сценария
обработки сообщения историей диалога (а вместе с ней и обоими
репозиториями) запланировано отдельной задачей Sprint 2 (S2-06,
backlog_2.md §9/§14). Функции ниже — точки сборки, которые эта будущая
задача сможет вызвать, передав уже открытую `AsyncSession`
(`infrastructure/persistence/session.py::session_scope`) — bootstrap не
создаёт и не хранит сессию заранее в глобальном состоянии.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from dekoder.application.conversation.ports import ConversationRepository
from dekoder.application.user.ports import UserRepository
from dekoder.infrastructure.persistence.conversation_repository import SQLAlchemyConversationRepository
from dekoder.infrastructure.persistence.user_repository import SQLAlchemyUserRepository


def build_user_repository(session: AsyncSession) -> UserRepository:
    """Собирает `UserRepository` поверх переданной `AsyncSession`."""
    return SQLAlchemyUserRepository(session)


def build_conversation_repository(session: AsyncSession) -> ConversationRepository:
    """Собирает `ConversationRepository` поверх переданной `AsyncSession`."""
    return SQLAlchemyConversationRepository(session)
