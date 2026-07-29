"""
RouteCommandUseCase — единственная точка, через которую interfaces/telegram
обращается к profile/session/skills/model_catalog/memory (docs/versions/03,
§7; docs/versions/05, §14: interfaces/telegram вызывает только
application/ai_core/). Тонкие проброс-методы, без собственной логики.
"""

from __future__ import annotations

from dekoder.application.memory.queries import DialogueEntryView, MemoryFactView
from dekoder.application.memory.use_cases.confirm_memory_fact import ConfirmMemoryFactUseCase
from dekoder.application.memory.use_cases.forget_memory_fact import ForgetMemoryFactUseCase
from dekoder.application.memory.use_cases.get_dialogue_history import GetDialogueHistoryUseCase
from dekoder.application.memory.use_cases.get_memory_facts import GetMemoryFactsUseCase
from dekoder.application.memory.use_cases.stage_memory_fact import StageMemoryFactUseCase
from dekoder.application.model_catalog.queries import ModelOptionView
from dekoder.application.model_catalog.use_cases.get_available_models import (
    GetAvailableModelsUseCase,
)
from dekoder.application.profile.queries import AuthorProfileView
from dekoder.application.profile.use_cases.archive_author_profile import (
    ArchiveAuthorProfileUseCase,
)
from dekoder.application.profile.use_cases.create_author_profile import (
    CreateAuthorProfileUseCase,
)
from dekoder.application.profile.use_cases.get_author_profiles import GetAuthorProfilesUseCase
from dekoder.application.profile.use_cases.set_default_profile import SetDefaultProfileUseCase
from dekoder.application.profile.use_cases.update_author_profile import (
    UpdateAuthorProfileUseCase,
)
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
from dekoder.domain.memory.fact import MemoryFact
from dekoder.domain.memory.fact_draft import MemoryFactDraft
from dekoder.shared.domain.identifiers import DraftId, SkillId, UserId
from dekoder.shared.domain.value_objects import ContentType, GenerationType


class RouteCommandUseCase:
    def __init__(
        self,
        create_author_profile: CreateAuthorProfileUseCase,
        update_author_profile: UpdateAuthorProfileUseCase,
        archive_author_profile: ArchiveAuthorProfileUseCase,
        set_default_profile: SetDefaultProfileUseCase,
        get_author_profiles: GetAuthorProfilesUseCase,
        get_available_skills: GetAvailableSkillsUseCase,
        start_generation_session: StartGenerationSessionUseCase,
        select_content_type: SelectContentTypeUseCase,
        select_skill: SelectSkillUseCase,
        select_model: SelectModelUseCase,
        submit_user_input: SubmitUserInputUseCase,
        cancel_session: CancelSessionUseCase,
        reset_session: ResetSessionUseCase,
        get_available_models: GetAvailableModelsUseCase,
        stage_memory_fact: StageMemoryFactUseCase,
        confirm_memory_fact: ConfirmMemoryFactUseCase,
        forget_memory_fact: ForgetMemoryFactUseCase,
        get_memory_facts: GetMemoryFactsUseCase,
        get_dialogue_history: GetDialogueHistoryUseCase,
    ) -> None:
        self._create_author_profile = create_author_profile
        self._update_author_profile = update_author_profile
        self._archive_author_profile = archive_author_profile
        self._set_default_profile = set_default_profile
        self._get_author_profiles = get_author_profiles
        self._get_available_skills = get_available_skills
        self._start_generation_session = start_generation_session
        self._select_content_type = select_content_type
        self._select_skill = select_skill
        self._select_model = select_model
        self._submit_user_input = submit_user_input
        self._cancel_session = cancel_session
        self._reset_session = reset_session
        self._get_available_models = get_available_models
        self._stage_memory_fact = stage_memory_fact
        self._confirm_memory_fact = confirm_memory_fact
        self._forget_memory_fact = forget_memory_fact
        self._get_memory_facts = get_memory_facts
        self._get_dialogue_history = get_dialogue_history

    def list_profiles(self, user_id: UserId) -> list[AuthorProfileView]:
        raise NotImplementedError

    def start_session(self, user_id: UserId) -> GenerationSessionView:
        raise NotImplementedError

    def list_available_skills(
        self, content_type: ContentType | None, generation_type: GenerationType
    ) -> list[SkillOptionView]:
        raise NotImplementedError

    def list_available_models(self, skill_id: SkillId, generation_type: GenerationType) -> list[ModelOptionView]:
        raise NotImplementedError

    def stage_fact(self, user_id: UserId, fact_text: str) -> MemoryFactDraft:
        raise NotImplementedError

    def confirm_fact(self, user_id: UserId, draft_id: DraftId) -> MemoryFact:
        raise NotImplementedError

    def list_facts(self, user_id: UserId) -> list[MemoryFactView]:
        raise NotImplementedError

    def list_dialogue_history(self, user_id: UserId, limit: int) -> list[DialogueEntryView]:
        raise NotImplementedError
