"""
RouteCommandUseCase — единственная точка, через которую interfaces/telegram
обращается к profile/session/skills/memory (docs/versions/03,
§7; docs/versions/05, §14: interfaces/telegram вызывает только
application/ai_core/). Тонкие проброс-методы, без собственной логики.
"""

from __future__ import annotations

from dekoder.application.session.queries import GenerationSessionView
from dekoder.application.session.use_cases.cancel_session import CancelSessionUseCase
from dekoder.application.session.use_cases.reset_session import ResetSessionUseCase
from dekoder.application.session.use_cases.select_content_type import SelectContentTypeUseCase
from dekoder.application.session.use_cases.select_model import SelectModelUseCase
from dekoder.application.session.use_cases.select_skill import SelectSkillUseCase
from dekoder.application.session.use_cases.start_generation_session import (
    StartGenerationSessionUseCase,
)
from dekoder.application.session.use_cases.submit_user_input import SubmitUserInputUseCase
from dekoder.application.skills.queries import SkillOptionView
from dekoder.application.skills.use_cases.get_available_skills import GetAvailableSkillsUseCase
from dekoder.shared.domain.identifiers import UserId
from dekoder.shared.domain.value_objects import ContentType, GenerationType


class RouteCommandUseCase:
    def __init__(
        self,
        get_available_skills: GetAvailableSkillsUseCase,
        start_generation_session: StartGenerationSessionUseCase,
        select_content_type: SelectContentTypeUseCase,
        select_skill: SelectSkillUseCase,
        select_model: SelectModelUseCase,
        submit_user_input: SubmitUserInputUseCase,
        cancel_session: CancelSessionUseCase,
        reset_session: ResetSessionUseCase,
    ) -> None:
        self._get_available_skills = get_available_skills
        self._start_generation_session = start_generation_session
        self._select_content_type = select_content_type
        self._select_skill = select_skill
        self._select_model = select_model
        self._submit_user_input = submit_user_input
        self._cancel_session = cancel_session
        self._reset_session = reset_session

    def start_session(self, user_id: UserId) -> GenerationSessionView:
        raise NotImplementedError

    def list_available_skills(
        self, content_type: ContentType | None, generation_type: GenerationType
    ) -> list[SkillOptionView]:
        raise NotImplementedError
