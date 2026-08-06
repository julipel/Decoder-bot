"""Тесты доменной сущности `AIModel` (domain/model_catalog/entities.py, задача S7-02)."""

from __future__ import annotations

import dataclasses

import pytest

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.model_catalog.entities import AIModel
from dekoder.domain.model_catalog.enums import (
    AIProvider,
    ModelAvailability,
    ModelCapability,
    ModelPriceTier,
)
from dekoder.domain.model_catalog.value_objects import GenerationSettings


def _make_model(**overrides: object) -> AIModel:
    defaults: dict[str, object] = {
        "model_id": ModelId("anthropic/claude-3.5-sonnet"),
        "display_name": "Claude 3.5 Sonnet",
        "provider": AIProvider.ANTHROPIC,
        "context_window": 200_000,
        "capabilities": frozenset({ModelCapability.TEXT, ModelCapability.VISION}),
        "price_tier": ModelPriceTier.HIGH,
        "availability": ModelAvailability.AVAILABLE,
        "recommended_for": ("код", "анализ"),
        "default_generation_settings": GenerationSettings(temperature=0.7, max_tokens=4096),
    }
    defaults.update(overrides)
    return AIModel(**defaults)  # type: ignore[arg-type]


class TestAIModelCreation:
    def test_creates_valid_model(self) -> None:
        model = _make_model()

        assert model.display_name == "Claude 3.5 Sonnet"
        assert model.provider is AIProvider.ANTHROPIC
        assert model.availability is ModelAvailability.AVAILABLE

    def test_model_id_is_live_value_object(self) -> None:
        model = _make_model()

        assert model.model_id == ModelId("anthropic/claude-3.5-sonnet")

    def test_accepts_capabilities_frozenset(self) -> None:
        model = _make_model(capabilities=frozenset({ModelCapability.TEXT}))

        assert model.capabilities == frozenset({ModelCapability.TEXT})

    def test_accepts_recommended_for_tuple(self) -> None:
        model = _make_model(recommended_for=("код",))

        assert model.recommended_for == ("код",)


class TestAIModelInvariants:
    def test_empty_display_name_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="display_name"):
            _make_model(display_name="")

    def test_blank_display_name_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="display_name"):
            _make_model(display_name="   ")

    def test_zero_context_window_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="context_window"):
            _make_model(context_window=0)

    def test_negative_context_window_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="context_window"):
            _make_model(context_window=-1)


class TestAIModelImmutability:
    def test_is_frozen(self) -> None:
        model = _make_model()

        with pytest.raises(dataclasses.FrozenInstanceError):
            model.display_name = "Другое"  # type: ignore[misc]


class TestModelCatalogEnumsArePlainEnum:
    """ADR-7.3: enum'ы — plain `Enum`, не `str, Enum` (стиль `ProfileStatus`/`MemoryCategory`)."""

    def test_ai_provider_is_not_str_subclass(self) -> None:
        assert not issubclass(AIProvider, str)

    def test_model_capability_is_not_str_subclass(self) -> None:
        assert not issubclass(ModelCapability, str)

    def test_model_availability_is_not_str_subclass(self) -> None:
        assert not issubclass(ModelAvailability, str)

    def test_model_price_tier_is_not_str_subclass(self) -> None:
        assert not issubclass(ModelPriceTier, str)


class TestAIModelHasNoExternalIdField:
    """ADR-7.3: нет отдельного поля «внешний идентификатор»/`technical_id` — `model_id.value` используется дважды."""

    def test_no_technical_id_field(self) -> None:
        field_names = {f.name for f in dataclasses.fields(AIModel)}

        assert "technical_id" not in field_names
        assert "external_id" not in field_names
