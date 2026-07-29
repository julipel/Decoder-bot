from __future__ import annotations

from dekoder.application.profile.ports import ProfileRepository
from dekoder.domain.profile.profile import AuthorProfile
from dekoder.infrastructure.persistence.sqlite_connection import SqliteConnectionFactory
from dekoder.shared.domain.identifiers import ProfileId, UserId


class SqliteProfileRepository(ProfileRepository):
    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def add(self, profile: AuthorProfile) -> None:
        raise NotImplementedError

    def get(self, profile_id: ProfileId) -> AuthorProfile | None:
        raise NotImplementedError

    def list_for_user(self, user_id: UserId) -> list[AuthorProfile]:
        raise NotImplementedError

    def update(self, profile: AuthorProfile) -> None:
        raise NotImplementedError

    def archive(self, profile_id: ProfileId) -> None:
        raise NotImplementedError
