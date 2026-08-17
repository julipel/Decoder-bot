"""
`admin_profiles_router` — защищённый REST-доступ к CRUD профилей
(Sprint 8, задача S8-08, ADR-8.8).

Все пять эндпоинтов защищены `require_admin_api_key` на уровне
`APIRouter` (ADR-8.2). Use case'ы получаются через уже существующий
`get_container(request)` (`bootstrap/application.py`) — те же четыре
поля `ApplicationContainer`, что собрал S8-07 (`create_profile`/
`update_profile`/`deactivate_profile`/`list_all_profiles`); НЕ добавляет
пятое поле «GetProfile» — ADR-8.4 checklist фиксирует ровно 4 новых поля
профилей в `ApplicationContainer`. `GET /{profile_id}` поэтому переиспользует
`list_all_profiles` и фильтрует по id в самом роуте (архитектурно
приемлемо — фильтрация происходит на уровне presentation, не через
прямой доступ к репозиторию; для MVP-объёма каталог профилей — считаные
десятки записей, не тысячи).

`archive` — `POST .../archive`, не `DELETE`: профили никогда не
удаляются физически, только архивируются (state transition, не
ресурс-деструкция). `PROFILE_ARCHIVE_DEFAULT_FORBIDDEN` (поднимается
`DeactivateProfile` как `ApplicationError`) долетает до клиента как 409
через глобальный `dekoder_error_handler` (S8-03/ADR-8.12) — роут не
перехватывает её отдельно.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from dekoder.application.profile.dto import (
    CreateProfileCommand,
    DeactivateProfileCommand,
    DeactivateProfileStatus,
    UpdateProfileCommand,
)
from dekoder.bootstrap.application import get_container
from dekoder.bootstrap.container import ApplicationContainer
from dekoder.domain.conversation.value_objects import ModelId
from dekoder.presentation.api.dependencies.auth import require_admin_api_key
from dekoder.presentation.api.schemas.profiles import CreateProfileRequest, ProfileResponse, UpdateProfileRequest
from dekoder.shared.errors import NotFoundError

router = APIRouter(prefix="/admin/profiles", tags=["admin-profiles"], dependencies=[Depends(require_admin_api_key)])


def _to_model_id(raw: str | None) -> ModelId | None:
    return ModelId(raw) if raw else None


@router.get("", response_model=list[ProfileResponse])
async def list_profiles(container: ApplicationContainer = Depends(get_container)) -> list[ProfileResponse]:
    result = await container.list_all_profiles.execute()
    return [ProfileResponse.model_validate(profile) for profile in result.profiles]


@router.post("", response_model=ProfileResponse, status_code=201)
async def create_profile(
    request: CreateProfileRequest, container: ApplicationContainer = Depends(get_container)
) -> ProfileResponse:
    command = CreateProfileCommand(
        name=request.name,
        description=request.description,
        system_instruction=request.system_instruction,
        response_style=request.response_style,
        target_audience=request.target_audience,
        formality_level=request.formality_level,
        preferred_structure=request.preferred_structure,
        forbidden_phrasing=request.forbidden_phrasing,
        preferred_model=_to_model_id(request.preferred_model),
        response_length_hint=request.response_length_hint,
        additional_constraints=request.additional_constraints,
    )
    profile = await container.create_profile.execute(command)
    return ProfileResponse.model_validate(profile)


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: UUID, container: ApplicationContainer = Depends(get_container)) -> ProfileResponse:
    result = await container.list_all_profiles.execute()
    profile = next((candidate for candidate in result.profiles if candidate.id == profile_id), None)
    if profile is None:
        raise NotFoundError(message=f"Профиль {profile_id} не найден", user_message="Профиль не найден.")
    return ProfileResponse.model_validate(profile)


@router.patch("/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: UUID, request: UpdateProfileRequest, container: ApplicationContainer = Depends(get_container)
) -> ProfileResponse:
    command = UpdateProfileCommand(
        profile_id=profile_id,
        name=request.name,
        description=request.description,
        system_instruction=request.system_instruction,
        response_style=request.response_style,
        target_audience=request.target_audience,
        formality_level=request.formality_level,
        preferred_structure=request.preferred_structure,
        forbidden_phrasing=request.forbidden_phrasing,
        preferred_model=_to_model_id(request.preferred_model),
        response_length_hint=request.response_length_hint,
        additional_constraints=request.additional_constraints,
    )
    updated = await container.update_profile.execute(command)
    if updated is None:
        raise NotFoundError(message=f"Профиль {profile_id} не найден", user_message="Профиль не найден.")
    return ProfileResponse.model_validate(updated)


@router.post("/{profile_id}/archive", response_model=ProfileResponse)
async def archive_profile(
    profile_id: UUID, container: ApplicationContainer = Depends(get_container)
) -> ProfileResponse:
    result = await container.deactivate_profile.execute(DeactivateProfileCommand(profile_id=profile_id))
    if result.status is DeactivateProfileStatus.UNKNOWN_PROFILE:
        raise NotFoundError(message=f"Профиль {profile_id} не найден", user_message="Профиль не найден.")
    assert result.profile is not None  # ARCHIVED всегда несёт профиль (application/profile/dto.py)
    return ProfileResponse.model_validate(result.profile)
