"""Внутренний коллаборатор ai_core — проверяет совместимость Skill с типом контента (docs/versions/05, §9)."""

from __future__ import annotations

from dekoder.application.skills.ports import ContentSkillRepository
from dekoder.domain.skills.skill import ContentSkill
from dekoder.shared.domain.identifiers import SkillId
from dekoder.shared.domain.value_objects import ContentType


class SkillResolver:
    """Может завершиться SkillNotFound/SkillIncompatible (05, §12)."""

    def __init__(self, content_skill_repository: ContentSkillRepository) -> None:
        self._content_skill_repository = content_skill_repository

    def resolve(self, skill_id: SkillId, content_type: ContentType) -> ContentSkill:
        raise NotImplementedError
