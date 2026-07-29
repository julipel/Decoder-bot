"""
ContentSkill — конфигурируемый сценарий генерации; только
seed/конфигурация, не runtime CRUD (docs/versions/04, §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from dekoder.shared.domain.identifiers import ModelId, SkillId
from dekoder.shared.domain.value_objects import ContentType, GenerationType


class SkillRagMode(str, Enum):
    DISABLED = "disabled"
    OPTIONAL = "optional"
    REQUIRED = "required"


@dataclass
class ContentSkill:
    skill_id: SkillId
    title: str
    generation_type: GenerationType
    content_types: tuple[ContentType, ...]
    required_input_fields: tuple[str, ...] = field(default_factory=tuple)
    rag_mode: SkillRagMode = SkillRagMode.DISABLED
    uses_memory: bool = True
    compatible_model_ids: tuple[ModelId, ...] = field(default_factory=tuple)
    prompt_template_ref: str = ""
