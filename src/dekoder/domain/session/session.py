"""
GenerationSession — состояние одного незавершённого пользовательского
сценария; не сохраняется после завершения (docs/versions/04, §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from dekoder.shared.domain.identifiers import ModelId, ProfileId, SessionId, SkillId, UserId
from dekoder.shared.domain.value_objects import ContentType, GenerationType


class SessionStep(str, Enum):
    SELECT_PROFILE = "select_profile"
    SELECT_CONTENT_TYPE = "select_content_type"
    SELECT_SKILL = "select_skill"
    SELECT_MODEL = "select_model"
    AWAITING_INPUT = "awaiting_input"
    READY_TO_GENERATE = "ready_to_generate"


class SessionStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class GenerationSession:
    session_id: SessionId
    user_id: UserId
    created_at: datetime
    status: SessionStatus = SessionStatus.CREATED
    current_step: SessionStep = SessionStep.SELECT_PROFILE
    selected_profile_id: ProfileId | None = None
    selected_skill_id: SkillId | None = None
    selected_model_id: ModelId | None = None
    content_type: ContentType | None = None
    generation_type: GenerationType | None = None
    user_input: dict[str, str] = field(default_factory=dict)
