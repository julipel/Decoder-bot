"""SQLite-реализация ProfileRepositoryPort (единая таблица профиля)."""

from __future__ import annotations

from dekoder.infrastructure.sqlite.connection import SqliteConnectionFactory
from dekoder.modules.profile.application.ports import ProfileRepositoryPort
from dekoder.modules.profile.domain.profile import Profile


class SqliteProfileRepository(ProfileRepositoryPort):
    """Хранит единственную запись профиля в SQLite. Создание таблиц — вне объёма задачи."""

    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def get_profile(self) -> Profile | None:
        raise NotImplementedError

    def save_profile(self, profile: Profile) -> None:
        raise NotImplementedError
