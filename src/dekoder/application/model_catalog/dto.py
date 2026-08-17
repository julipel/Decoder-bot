"""
DTO прикладного слоя каталога моделей (Sprint 7, задача S7-05) —
вход/выход `ListAvailableModels`/`GetSelectedModel`/`SelectModel`.

Тот же стиль, что и `application/profile/dto.py`/`application/memory/
dto.py`: обычные `dataclass(frozen=True)`, без Pydantic и без привязки к
Telegram SDK — внутренний контракт application-слоя. Команды несут
`telegram_user_id: int` (не `user_id: UUID` напрямую) — тот же принцип,
что и `GetActiveProfileCommand`/`ListMemoryRecordsCommand`: use case сам
резолвит `telegram_user_id` в доменного `User` через `repositories.users`,
presentation-слой не знает про доменный `UUID`.
"""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.model_catalog.entities import AIModel
from dekoder.shared.domain.identifiers import CorrelationId


@dataclass(frozen=True)
class ListAvailableModelsCommand:
    telegram_user_id: int
    correlation_id: CorrelationId


@dataclass(frozen=True)
class ListAvailableModelsResult:
    """`active_model_id` — персональный выбор пользователя, если сделан и известен репозиторию; иначе `None`."""

    models: tuple[AIModel, ...]
    active_model_id: ModelId | None


@dataclass(frozen=True)
class GetSelectedModelCommand:
    telegram_user_id: int
    correlation_id: CorrelationId


@dataclass(frozen=True)
class GetSelectedModelResult:
    """
    `model is None`, если: пользователь неизвестен, персональный выбор не
    сделан, или выбор указывает на `model_id`, которого больше нет в
    текущем каталоге (устойчивость к изменению каталога после того, как
    выбор был сделан, ADR-7.7 AC-3) — все три штатные, неразличаемые для
    вызывающего кода отрицательные исходы, не исключения.
    """

    model: AIModel | None


@dataclass(frozen=True)
class SelectModelCommand:
    telegram_user_id: int
    model_id: ModelId
    correlation_id: CorrelationId


@dataclass(frozen=True)
class SelectModelResult:
    """Заполняется только при успехе — при отказе `SelectModel` поднимает `ApplicationError`, а не результат."""

    model: AIModel
