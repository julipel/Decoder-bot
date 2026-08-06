"""
In-memory fake `ModelCatalogRepository` (`application/model_catalog/
ports.py`) — общий тестовый helper для юнит-тестов use case'ов каталога
моделей (Sprint 7, задача S7-05) и `ProcessUserMessage` (S7-06), по тому
же принципу, что `tests/support/fake_conversation_repositories.py`.

Никакого JSON/файлового I/O — только словарь в памяти, по образцу
`FakeProfileRepository`/`FakeMemoryRepository`.
"""

from __future__ import annotations

from collections.abc import Sequence

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.model_catalog.entities import AIModel
from dekoder.domain.model_catalog.enums import (
    AIProvider,
    ModelAvailability,
    ModelCapability,
    ModelPriceTier,
)
from dekoder.domain.model_catalog.value_objects import GenerationSettings


def make_ai_model(
    model_id: str = "openai/gpt-4o-mini",
    *,
    display_name: str = "GPT-4o mini",
    provider: AIProvider = AIProvider.OPENAI,
    context_window: int = 128_000,
    capabilities: frozenset[ModelCapability] = frozenset({ModelCapability.TEXT}),
    price_tier: ModelPriceTier = ModelPriceTier.LOW,
    availability: ModelAvailability = ModelAvailability.AVAILABLE,
    recommended_for: tuple[str, ...] = (),
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> AIModel:
    """Строит тестовый `AIModel` с разумными значениями по умолчанию — по образцу `_make_profile`/`_make_record`."""
    return AIModel(
        model_id=ModelId(model_id),
        display_name=display_name,
        provider=provider,
        context_window=context_window,
        capabilities=capabilities,
        price_tier=price_tier,
        availability=availability,
        recommended_for=recommended_for,
        default_generation_settings=GenerationSettings(temperature=temperature, max_tokens=max_tokens),
    )


class FakeModelCatalogRepository:
    """In-memory fake порта `ModelCatalogRepository` (Sprint 7, задача S7-03/S7-05)."""

    def __init__(self, models: Sequence[AIModel] | None = None) -> None:
        catalog = models if models is not None else [make_ai_model()]
        self._by_id: dict[ModelId, AIModel] = {model.model_id: model for model in catalog}

    def get(self, model_id: ModelId) -> AIModel | None:
        return self._by_id.get(model_id)

    def list_all(self) -> Sequence[AIModel]:
        return list(self._by_id.values())
