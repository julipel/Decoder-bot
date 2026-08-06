"""
Доменные сущности каталога AI-моделей (Sprint 7, задачи S7-02/S7-04,
ADR-7.2/ADR-7.3/ADR-7.5) — `AIModel` (запись статичного каталога) и
`ModelSelection` (персональный выбор пользователя), реализующие Этап 9
«Плана реализации.md» (выбор AI-модели пользователем).

Плоские `frozen`-датаклассы, стиль `domain/profile/entities.py::
UserProfile`/`domain/memory/entities.py::MemoryRecord`.

`model_id: ModelId` — переиспользует живой `domain/conversation/
value_objects.ModelId` (ADR-7.2), не создаёт новый тип и не импортирует
мёртвый `shared/domain/identifiers.ModelId`. Та же строка одновременно
служит и внутренним каталожным ключом, и значением, уходящим в
`LLMRequest.model_id` — отдельного поля «внешний идентификатор» нет
(ADR-7.3): OpenRouter уже сам федерирует всех поставщиков одним
HTTP-интерфейсом, поэтому дополнительный слой трансляции не оправдан
(YAGNI).

`context_window`, `capabilities`, `price_tier`, `recommended_for` —
информационные поля MVP, отображаются в `/model`, но не участвуют ни в
`TokenBudgetPolicy`, ни в какой-либо логике выбора/отказа (ADR-7.3).
`default_generation_settings` — единственное поле, реально используемое
`ProcessUserMessage` (ADR-7.7).

`ModelSelection` (ADR-7.5) — персональный выбор модели одним
пользователем; `user_id`/`selected_at` — плоские `UUID`/`datetime`, без
обёрток, по конвенции `MemoryRecord.user_id`. `ModelSelectionRepository`
(`application/model_catalog/ports.py`) оперирует напрямую `ModelId` (не
этой сущностью) в своих сигнатурах — по тому же прецеденту, что и
`user_active_profiles` (ADR-3.1): у связи «пользователь → выбор» нет
собственного поведения, только атомарная замена значения.

Ноль зависимостей от SQLAlchemy/Telegram/FastAPI/JSON — чистый Python, как
`domain/profile/entities.py`. Ошибки — обычный `ValueError`, отдельная
доменная ошибка не оправдана (claude.md §20, по прецеденту `UserProfile`/
`MemoryRecord`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.model_catalog.enums import (
    AIProvider,
    ModelAvailability,
    ModelCapability,
    ModelPriceTier,
)
from dekoder.domain.model_catalog.value_objects import GenerationSettings


@dataclass(frozen=True, slots=True)
class AIModel:
    """Запись каталога AI-моделей — модель, доступная для выбора пользователем через `/model`."""

    model_id: ModelId
    display_name: str
    provider: AIProvider
    context_window: int
    capabilities: frozenset[ModelCapability]
    price_tier: ModelPriceTier
    availability: ModelAvailability
    recommended_for: tuple[str, ...]
    default_generation_settings: GenerationSettings

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValueError("display_name не может быть пустым")
        if self.context_window <= 0:
            raise ValueError("context_window должен быть положительным")


@dataclass(frozen=True, slots=True)
class ModelSelection:
    """Персональный выбор AI-модели одним пользователем — запись `user_active_models` (ADR-7.5)."""

    user_id: UUID
    model_id: ModelId
    selected_at: datetime
