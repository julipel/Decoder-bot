"""
Pydantic-схемы admin REST для профилей (Sprint 8, задача S8-08,
ADR-8.7/8.8).

`CreateProfileRequest`/`UpdateProfileRequest` физически НЕ содержат полей
`is_default`/`is_system`/`status` — не просто «не читаются», а
отсутствуют как поля схемы: `CreateProfile` всегда создаёт профиль с
`is_system=False, is_default=False`; `status` меняется только через
отдельный `POST /admin/profiles/{id}/archive`.

`preferred_model` — простая строка на границе REST (не доменный
`ModelId`) — маршруты сами оборачивают/разворачивают `ModelId` на входе/
выходе (`_to_model_id`/`ProfileResponse`'s `field_validator`).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.profile.value_objects import ProfileStatus


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    system_instruction: str
    response_style: str
    target_audience: str
    formality_level: str
    preferred_structure: str
    forbidden_phrasing: tuple[str, ...]
    preferred_model: str | None
    response_length_hint: str | None
    additional_constraints: str
    status: ProfileStatus
    is_system: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("preferred_model", mode="before")
    @classmethod
    def _unwrap_model_id(cls, value: object) -> str | None:
        if isinstance(value, ModelId):
            return value.value
        return value  # type: ignore[return-value]


class CreateProfileRequest(BaseModel):
    """Вход `POST /admin/profiles`. Без `is_default`/`is_system`/`status` — эти поля не settable через admin REST."""

    name: str
    description: str
    system_instruction: str
    response_style: str
    target_audience: str
    formality_level: str
    preferred_structure: str
    forbidden_phrasing: tuple[str, ...] = ()
    preferred_model: str | None = None
    response_length_hint: str | None = None
    additional_constraints: str = ""


class UpdateProfileRequest(BaseModel):
    """
    Вход `PATCH /admin/profiles/{id}` — частичное обновление, все поля
    опциональны. Без `is_default`/`is_system`/`status` — read-only через
    этот эндпоинт; `status` меняется только через `POST .../archive`.
    """

    name: str | None = None
    description: str | None = None
    system_instruction: str | None = None
    response_style: str | None = None
    target_audience: str | None = None
    formality_level: str | None = None
    preferred_structure: str | None = None
    forbidden_phrasing: tuple[str, ...] | None = None
    preferred_model: str | None = None
    response_length_hint: str | None = None
    additional_constraints: str | None = None
