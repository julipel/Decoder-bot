"""
Интеграционные тесты `ConfigModelCatalogRepository` (Sprint 7, задача
S7-03, ADR-7.4) — часть их — round-trip на временном JSON-файле (`tmp_path`,
по стилю `test_file_template_repository.py`), часть — на реальном
сид-каталоге `infrastructure/model_catalog/catalog.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.model_catalog.enums import AIProvider, ModelAvailability, ModelCapability
from dekoder.infrastructure.model_catalog.config_repository import (
    DEFAULT_CATALOG_PATH,
    ConfigModelCatalogRepository,
)
from dekoder.shared.errors import InfrastructureError


def _write_catalog(path: Path, entries: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(entries), encoding="utf-8")


def _valid_entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "model_id": "openai/gpt-4o-mini",
        "display_name": "GPT-4o mini",
        "provider": "openai",
        "context_window": 128000,
        "capabilities": ["text", "vision"],
        "price_tier": "low",
        "availability": "available",
        "recommended_for": ["общие задачи"],
        "default_generation_settings": {"temperature": 0.7, "max_tokens": 1024},
    }
    entry.update(overrides)
    return entry


class TestConfigModelCatalogRepositoryRoundTrip:
    def test_list_all_returns_expected_number_of_models(self, tmp_path: Path) -> None:
        catalog_path = tmp_path / "catalog.json"
        _write_catalog(
            catalog_path,
            [
                _valid_entry(model_id="openai/gpt-4o-mini"),
                _valid_entry(model_id="anthropic/claude-3.5-sonnet", provider="anthropic"),
            ],
        )

        repository = ConfigModelCatalogRepository(catalog_path=catalog_path)

        assert len(repository.list_all()) == 2

    def test_get_finds_existing_model(self, tmp_path: Path) -> None:
        catalog_path = tmp_path / "catalog.json"
        _write_catalog(catalog_path, [_valid_entry(model_id="openai/gpt-4o-mini")])

        repository = ConfigModelCatalogRepository(catalog_path=catalog_path)
        model = repository.get(ModelId("openai/gpt-4o-mini"))

        assert model is not None
        assert model.display_name == "GPT-4o mini"
        assert model.provider is AIProvider.OPENAI
        assert model.capabilities == frozenset({ModelCapability.TEXT, ModelCapability.VISION})

    def test_get_returns_none_for_unknown_model(self, tmp_path: Path) -> None:
        catalog_path = tmp_path / "catalog.json"
        _write_catalog(catalog_path, [_valid_entry(model_id="openai/gpt-4o-mini")])

        repository = ConfigModelCatalogRepository(catalog_path=catalog_path)

        assert repository.get(ModelId("does-not-exist/model")) is None

    def test_parses_unavailable_model(self, tmp_path: Path) -> None:
        catalog_path = tmp_path / "catalog.json"
        _write_catalog(catalog_path, [_valid_entry(availability="unavailable")])

        repository = ConfigModelCatalogRepository(catalog_path=catalog_path)
        model = repository.get(ModelId("openai/gpt-4o-mini"))

        assert model is not None
        assert model.availability is ModelAvailability.UNAVAILABLE

    def test_uses_configured_path_not_hardcoded(self, tmp_path: Path) -> None:
        catalog_path = tmp_path / "custom_name.json"
        _write_catalog(catalog_path, [_valid_entry(model_id="only/here")])

        repository = ConfigModelCatalogRepository(catalog_path=catalog_path)

        assert repository.get(ModelId("only/here")) is not None


class TestConfigModelCatalogRepositoryFailFast:
    def test_missing_file_raises_infrastructure_error(self, tmp_path: Path) -> None:
        with pytest.raises(InfrastructureError, match="каталог"):
            ConfigModelCatalogRepository(catalog_path=tmp_path / "does_not_exist.json")

    def test_malformed_json_raises_infrastructure_error(self, tmp_path: Path) -> None:
        catalog_path = tmp_path / "catalog.json"
        catalog_path.write_text("{not valid json", encoding="utf-8")

        with pytest.raises(InfrastructureError, match="повреждён"):
            ConfigModelCatalogRepository(catalog_path=catalog_path)

    def test_missing_required_field_raises_infrastructure_error(self, tmp_path: Path) -> None:
        catalog_path = tmp_path / "catalog.json"
        entry = _valid_entry()
        del entry["display_name"]
        _write_catalog(catalog_path, [entry])

        with pytest.raises(InfrastructureError, match="невалидную запись"):
            ConfigModelCatalogRepository(catalog_path=catalog_path)

    def test_invalid_enum_value_raises_infrastructure_error(self, tmp_path: Path) -> None:
        catalog_path = tmp_path / "catalog.json"
        _write_catalog(catalog_path, [_valid_entry(provider="unknown-provider")])

        with pytest.raises(InfrastructureError, match="невалидную запись"):
            ConfigModelCatalogRepository(catalog_path=catalog_path)

    def test_invalid_domain_invariant_raises_infrastructure_error(self, tmp_path: Path) -> None:
        catalog_path = tmp_path / "catalog.json"
        _write_catalog(catalog_path, [_valid_entry(display_name="   ")])

        with pytest.raises(InfrastructureError, match="невалидную запись"):
            ConfigModelCatalogRepository(catalog_path=catalog_path)


class TestSeedCatalog:
    """Проверяет реальный сид-каталог `infrastructure/model_catalog/catalog.json`."""

    def test_default_catalog_path_is_used_without_explicit_argument(self) -> None:
        repository = ConfigModelCatalogRepository()

        assert len(repository.list_all()) >= 4

    def test_seed_catalog_covers_at_least_two_providers(self) -> None:
        repository = ConfigModelCatalogRepository()

        providers = {model.provider for model in repository.list_all()}

        assert AIProvider.OPENAI in providers
        assert AIProvider.ANTHROPIC in providers

    def test_catalog_path_constant_points_at_seed_file(self) -> None:
        assert DEFAULT_CATALOG_PATH.name == "catalog.json"
        assert DEFAULT_CATALOG_PATH.exists()
