from __future__ import annotations

from dekoder.application.skills.ports import ContentSkillRepository
from dekoder.application.skills.queries import GetAvailableSkillsQuery, SkillOptionView


class GetAvailableSkillsUseCase:
    def __init__(self, content_skill_repository: ContentSkillRepository) -> None:
        self._content_skill_repository = content_skill_repository

    def execute(self, query: GetAvailableSkillsQuery) -> list[SkillOptionView]:
        raise NotImplementedError
