"""ContentSkillRepository — чтение каталога Content Skills; без записи в runtime (docs/versions/05, §7)."""

from __future__ import annotations

from typing import Protocol

from dekoder.domain.skills.skill import ContentSkill
from dekoder.shared.domain.identifiers import SkillId
from dekoder.shared.domain.value_objects import GenerationType


class ContentSkillRepository(Protocol):
    def get(self, skill_id: SkillId) -> ContentSkill | None: ...

    def list_all(self) -> list[ContentSkill]: ...

    def list_by_generation_type(self, generation_type: GenerationType) -> list[ContentSkill]: ...
