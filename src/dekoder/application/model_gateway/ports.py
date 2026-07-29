"""
ModelGateway — единая точка вызова генеративной модели (TEXT/IMAGE),
не зависящая от поставщика (docs/versions/02, §8). Заменяет v1 LLMPort:
модальность-агностичный, замена LLMRequestContext/LLMResponse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from dekoder.shared.domain.identifiers import ModelId
from dekoder.shared.domain.value_objects import GenerationType, Prompt


@dataclass(frozen=True)
class ModelGatewayRequest:
    model_id: ModelId
    generation_type: GenerationType
    instruction: Prompt


@dataclass(frozen=True)
class ModelGatewayResult:
    status: str
    text: str | None
    image_ref: str | None
    provider_used: str
    model_used: str
    duration_ms: float | None
    error: str | None


class ModelGateway(Protocol):
    def generate(self, request: ModelGatewayRequest) -> ModelGatewayResult: ...
