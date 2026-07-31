"""
Bootstrap-фабрики репозиториев (Sprint 2, задача S2-03).

Единственное место, которому разрешено знать одновременно про порт
`UserRepository` (`application/user/ports.py`) и его конкретную
SQLAlchemy-реализацию (`infrastructure/persistence/user_repository.py`)
— то же правило единственной точки сборки, что и у
`bootstrap/container.py` для `LLMProvider` (claude.md §8.5, §29).

Задача S2-03 намеренно НЕ подключает эту фабрику ни в
`ApplicationContainer`, ни в `ProcessUserMessage` — расширение сценария
обработки сообщения историей диалога (а вместе с ней и `UserRepository`)
запланировано отдельной задачей Sprint 2 (S2-06, backlog_2.md §9/§14).
Функция ниже — точка сборки, которую эта будущая задача сможет вызвать,
передав уже открытую `AsyncSession` (`infrastructure/persistence/
session.py::session_scope`) — bootstrap не создаёт и не хранит сессию
заранее в глобальном состоянии.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from dekoder.application.user.ports import UserRepository
from dekoder.infrastructure.persistence.user_repository import SQLAlchemyUserRepository


def build_user_repository(session: AsyncSession) -> UserRepository:
    """Собирает `UserRepository` поверх переданной `AsyncSession`."""
    return SQLAlchemyUserRepository(session)
