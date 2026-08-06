"""Тесты `GenerationSettings` (domain/model_catalog/value_objects.py, задача S7-02)."""

from __future__ import annotations

import dataclasses

import pytest

from dekoder.domain.model_catalog.value_objects import GenerationSettings


class TestGenerationSettingsCreation:
    def test_creates_valid_settings(self) -> None:
        settings = GenerationSettings(temperature=0.7, max_tokens=2048)

        assert settings.temperature == 0.7
        assert settings.max_tokens == 2048

    def test_accepts_boundary_temperature_zero(self) -> None:
        settings = GenerationSettings(temperature=0.0, max_tokens=1)

        assert settings.temperature == 0.0

    def test_accepts_boundary_temperature_two(self) -> None:
        settings = GenerationSettings(temperature=2.0, max_tokens=1)

        assert settings.temperature == 2.0


class TestGenerationSettingsInvariants:
    def test_negative_temperature_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="temperature"):
            GenerationSettings(temperature=-0.1, max_tokens=100)

    def test_temperature_above_two_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="temperature"):
            GenerationSettings(temperature=2.5, max_tokens=100)

    def test_zero_max_tokens_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_tokens"):
            GenerationSettings(temperature=0.7, max_tokens=0)

    def test_negative_max_tokens_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_tokens"):
            GenerationSettings(temperature=0.7, max_tokens=-1)


class TestGenerationSettingsImmutability:
    def test_is_frozen(self) -> None:
        settings = GenerationSettings(temperature=0.7, max_tokens=100)

        with pytest.raises(dataclasses.FrozenInstanceError):
            settings.temperature = 1.0  # type: ignore[misc]
