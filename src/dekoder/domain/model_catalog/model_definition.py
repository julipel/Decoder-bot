"""
ModelDefinition — одна запись каталога моделей; ModelId уникален,
определяется конфигурацией/seed (docs/versions/04, §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from dekoder.shared.domain.identifiers import ModelId
from dekoder.shared.domain.value_objects import ContentType, GenerationType


class ModelAvailabilityStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass
class ModelDefinition:
    model_id: ModelId
    display_name: str
    provider: str
    technical_id: str
    supported_modalities: tuple[GenerationType, ...] = field(default_factory=tuple)
    supported_content_types: tuple[ContentType, ...] = field(default_factory=tuple)
    availability_status: ModelAvailabilityStatus = ModelAvailabilityStatus.AVAILABLE
