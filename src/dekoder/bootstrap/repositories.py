"""
Bootstrap-фабрики репозиториев (Sprint 2, задачи S2-03/S2-04/S2-05/S2-06;
Sprint 3, задача S3-05, ADR-3.3; Sprint 5, задача S5-03/S5-04, ADR-5.5;
Sprint 7, задача S7-04, ADR-7.5).

Единственное место, которому разрешено знать одновременно про порты
`UserRepository`/`ConversationRepository`/`MessageRepository`/
`ProfileRepository`/`MemoryRepository`/`ModelSelectionRepository`
(`application/user/ports.py`, `application/conversation/ports.py`,
`application/profile/ports.py`, `application/memory/ports.py`,
`application/model_catalog/ports.py`) и их конкретные
SQLAlchemy-реализации (`infrastructure/persistence/{user_repository.py,
conversation_repository.py, message_repository.py, profile_repository.py,
memory_repository.py, sqlalchemy_model_selection_repository.py}`) — то же
правило единственной точки сборки, что и у `bootstrap/container.py` для
`LLMProvider` (claude.md §8.5, §29).

`build_user_repository`/`build_conversation_repository`/
`build_message_repository`/`build_profile_repository`/
`build_memory_repository`/`build_model_selection_repository`
(S2-03/S2-04/S2-05/S3-05/S5-04/S7-04) собирают один репозиторий поверх
уже открытой `AsyncSession` — низкоуровневые строительные блоки.

`build_conversation_repositories_factory` (S2-06) — точка сборки, которую
использует `ProcessUserMessage` (через `ConversationRepositoriesFactory`,
`application/conversation/ports.py`): каждый вызов возвращённой фабрики
открывает НОВУЮ короткую транзакцию поверх `session_scope()`
(`infrastructure/persistence/session.py`, задача S2-01) — commit при
успешном выходе из `async with`, rollback при исключении, сессия
закрывается в обоих случаях — и отдаёт `ConversationRepositories`,
собранные тремя функциями выше поверх этой сессии. `ProcessUserMessage`
сам не создаёт и не закрывает `AsyncSession` и не импортирует
SQLAlchemy — этим по-прежнему занимается только bootstrap.

`build_knowledge_document_repository` (Sprint 6, задача S6-09) собирает
`KnowledgeDocumentRepository` тем же приёмом, что и функции выше — но не
входит в `ConversationRepositories`/`build_conversation_repositories_factory`
(ADR-6.4/6.6): база знаний не участвует в транзакции `ProcessUserMessage`,
у неё свой вызывающий код — `bootstrap/knowledge_container.py`, поверх
собственной, отдельной `session_scope()`, открываемой
`scripts/index_document.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dekoder.application.conversation.ports import (
    ConversationRepositories,
    ConversationRepositoriesFactory,
    ConversationRepository,
    MessageRepository,
)
from dekoder.application.knowledge.ports import KnowledgeDocumentRepository
from dekoder.application.memory.ports import MemoryRepository
from dekoder.application.model_catalog.ports import ModelSelectionRepository
from dekoder.application.profile.ports import ProfileRepository
from dekoder.application.user.ports import UserRepository
from dekoder.infrastructure.persistence.conversation_repository import SQLAlchemyConversationRepository
from dekoder.infrastructure.persistence.knowledge_document_repository import SQLAlchemyKnowledgeDocumentRepository
from dekoder.infrastructure.persistence.memory_repository import SQLAlchemyMemoryRepository
from dekoder.infrastructure.persistence.message_repository import SQLAlchemyMessageRepository
from dekoder.infrastructure.persistence.profile_repository import SQLAlchemyProfileRepository
from dekoder.infrastructure.persistence.session import session_scope
from dekoder.infrastructure.persistence.sqlalchemy_model_selection_repository import (
    SQLAlchemyModelSelectionRepository,
)
from dekoder.infrastructure.persistence.user_repository import SQLAlchemyUserRepository


def build_user_repository(session: AsyncSession) -> UserRepository:
    """Собирает `UserRepository` поверх переданной `AsyncSession`."""
    return SQLAlchemyUserRepository(session)


def build_conversation_repository(session: AsyncSession) -> ConversationRepository:
    """Собирает `ConversationRepository` поверх переданной `AsyncSession`."""
    return SQLAlchemyConversationRepository(session)


def build_message_repository(session: AsyncSession) -> MessageRepository:
    """Собирает `MessageRepository` поверх переданной `AsyncSession`."""
    return SQLAlchemyMessageRepository(session)


def build_profile_repository(session: AsyncSession) -> ProfileRepository:
    """Собирает `ProfileRepository` поверх переданной `AsyncSession` (Sprint 3, задача S3-05)."""
    return SQLAlchemyProfileRepository(session)


def build_memory_repository(session: AsyncSession) -> MemoryRepository:
    """Собирает `MemoryRepository` поверх переданной `AsyncSession` (Sprint 5, задача S5-04)."""
    return SQLAlchemyMemoryRepository(session)


def build_model_selection_repository(session: AsyncSession) -> ModelSelectionRepository:
    """Собирает `ModelSelectionRepository` поверх переданной `AsyncSession` (Sprint 7, задача S7-04, ADR-7.5)."""
    return SQLAlchemyModelSelectionRepository(session)


def build_knowledge_document_repository(session: AsyncSession) -> KnowledgeDocumentRepository:
    """Собирает `KnowledgeDocumentRepository` поверх переданной `AsyncSession` (Sprint 6, задача S6-09)."""
    return SQLAlchemyKnowledgeDocumentRepository(session)


def build_conversation_repositories_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> ConversationRepositoriesFactory:
    """
    Собирает `ConversationRepositoriesFactory` поверх единой фабрики сессий
    (`bootstrap/database.py::init_database`). Каждый вызов возвращённого
    callable — новая независимая короткая транзакция (`session_scope()`
    открывает `AsyncSession`, `ConversationRepositories` строятся поверх
    неё тремя функциями выше, коммит/rollback/close — на выходе из
    `async with`).
    """

    @asynccontextmanager
    async def _open_repositories() -> AsyncIterator[ConversationRepositories]:
        async with session_scope(session_factory) as session:
            yield ConversationRepositories(
                users=build_user_repository(session),
                conversations=build_conversation_repository(session),
                messages=build_message_repository(session),
                profiles=build_profile_repository(session),
                memory=build_memory_repository(session),
                model_selection=build_model_selection_repository(session),
            )

    return _open_repositories
