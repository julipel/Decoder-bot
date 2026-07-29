from __future__ import annotations

from dekoder.application.skills.ports import ContentSkillRepository
from dekoder.domain.skills.skill import ContentSkill
from dekoder.infrastructure.persistence.sqlite_connection import SqliteConnectionFactory
from dekoder.shared.domain.identifiers import SkillId
from dekoder.shared.domain.value_objects import GenerationType


class SqliteContentSkillRepository(ContentSkillRepository):
    """Read-only: каталог Content Skills — только seed/конфигурация (docs/versions/02, §6)."""

    def __init__(self, connection_factory: SqliteConnectionFactory) -> None:
        self._connection_factory = connection_factory

    def get(self, skill_id: SkillId) -> ContentSkill | None:
        raise NotImplementedError

    def list_all(self) -> list[ContentSkill]:
        raise NotImplementedError

    def list_by_generation_type(self, generation_type: GenerationType) -> list[ContentSkill]:
        raise NotImplementedError
