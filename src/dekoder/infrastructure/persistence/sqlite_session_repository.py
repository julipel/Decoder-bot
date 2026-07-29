from __future__ import annotations

from dekoder.application.session.ports import SessionRepository
from dekoder.domain.session.session import GenerationSession
from dekoder.infrastructure.persistence.sqlite_connection import SqliteConnectionFactory
from dekoder.shared.domain.identifiers import SessionId, UserId


class SqliteSessionRepository(SessionRepository):
    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def create(self, user_id: UserId) -> GenerationSession:
        raise NotImplementedError

    def get(self, session_id: SessionId) -> GenerationSession | None:
        raise NotImplementedError

    def get_active_for_user(self, user_id: UserId) -> GenerationSession | None:
        raise NotImplementedError

    def update(self, session: GenerationSession) -> None:
        raise NotImplementedError

    def delete(self, session_id: SessionId) -> None:
        raise NotImplementedError
