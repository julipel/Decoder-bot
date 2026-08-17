"""
Тесты централизованной конфигурации (docs-задача: pydantic-settings).

Каждый тест явно передаёт `_env_file=None` там, где важны значения по
умолчанию или ошибки валидации, — иначе реальный `.env.local`
разработчика (см. README «Быстрый старт») мог бы незаметно повлиять на
результат. Для сценариев «загрузка из окружения» `monkeypatch.setenv`
всегда имеет приоритет над файлом, поэтому изоляция не требуется.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from dekoder.shared.config import (
    AdminSettings,
    ApplicationSettings,
    DatabaseSettings,
    LLMProviderSettings,
    LLMSettings,
    ModelCatalogSettings,
    PromptSettings,
    Settings,
    TelegramSettings,
)


class TestApplicationSettingsDefaults:
    def test_default_values(self) -> None:
        settings = ApplicationSettings(_env_file=None)

        assert settings.name == "dekoder"
        assert settings.environment == "development"
        assert settings.debug is False
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000

    def test_loaded_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_NAME", "dekoder-staging")
        monkeypatch.setenv("APP_PORT", "9000")
        monkeypatch.setenv("APP_DEBUG", "true")

        settings = ApplicationSettings(_env_file=None)

        assert settings.name == "dekoder-staging"
        assert settings.port == 9000
        assert settings.debug is True

    @pytest.mark.parametrize("invalid_port", [0, -1, 65536, 100_000])
    def test_invalid_port_raises_validation_error(self, monkeypatch: pytest.MonkeyPatch, invalid_port: int) -> None:
        monkeypatch.setenv("APP_PORT", str(invalid_port))

        with pytest.raises(ValidationError):
            ApplicationSettings(_env_file=None)

    @pytest.mark.parametrize("valid_port", [1, 8000, 65535])
    def test_boundary_ports_are_accepted(self, monkeypatch: pytest.MonkeyPatch, valid_port: int) -> None:
        monkeypatch.setenv("APP_PORT", str(valid_port))

        settings = ApplicationSettings(_env_file=None)

        assert settings.port == valid_port


class TestLLMSettingsDefaults:
    def test_default_values(self) -> None:
        settings = LLMSettings(_env_file=None)

        assert settings.timeout == 30.0
        assert settings.max_tokens == 1024
        assert settings.temperature == 0.7

    def test_loaded_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_TIMEOUT", "15.5")
        monkeypatch.setenv("LLM_MAX_TOKENS", "2048")
        monkeypatch.setenv("LLM_TEMPERATURE", "1.2")

        settings = LLMSettings(_env_file=None)

        assert settings.timeout == 15.5
        assert settings.max_tokens == 2048
        assert settings.temperature == 1.2

    @pytest.mark.parametrize("invalid_timeout", [0, -1, -30.5])
    def test_invalid_timeout_raises_validation_error(
        self, monkeypatch: pytest.MonkeyPatch, invalid_timeout: float
    ) -> None:
        monkeypatch.setenv("LLM_TIMEOUT", str(invalid_timeout))

        with pytest.raises(ValidationError):
            LLMSettings(_env_file=None)

    @pytest.mark.parametrize("invalid_max_tokens", [0, -1])
    def test_invalid_max_tokens_raises_validation_error(
        self, monkeypatch: pytest.MonkeyPatch, invalid_max_tokens: int
    ) -> None:
        monkeypatch.setenv("LLM_MAX_TOKENS", str(invalid_max_tokens))

        with pytest.raises(ValidationError):
            LLMSettings(_env_file=None)

    @pytest.mark.parametrize("invalid_temperature", [-0.1, 2.1, 5.0])
    def test_invalid_temperature_raises_validation_error(
        self, monkeypatch: pytest.MonkeyPatch, invalid_temperature: float
    ) -> None:
        monkeypatch.setenv("LLM_TEMPERATURE", str(invalid_temperature))

        with pytest.raises(ValidationError):
            LLMSettings(_env_file=None)

    @pytest.mark.parametrize("valid_temperature", [0.0, 0.7, 2.0])
    def test_boundary_temperatures_are_accepted(
        self, monkeypatch: pytest.MonkeyPatch, valid_temperature: float
    ) -> None:
        monkeypatch.setenv("LLM_TEMPERATURE", str(valid_temperature))

        settings = LLMSettings(_env_file=None)

        assert settings.temperature == valid_temperature


class TestDatabaseSettingsDefaults:
    def test_default_value_is_a_relative_sqlite_url(self) -> None:
        settings = DatabaseSettings(_env_file=None)

        assert settings.url == "sqlite+aiosqlite:///./data/app.db"
        # без зависимости от абсолютного локального пути конкретной машины
        assert not settings.url.startswith("sqlite+aiosqlite:////")

    def test_can_be_overridden_via_environment_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./data/custom.db")

        settings = DatabaseSettings(_env_file=None)

        assert settings.url == "sqlite+aiosqlite:///./data/custom.db"

    def test_can_be_overridden_directly_in_tests_without_environment(self) -> None:
        settings = DatabaseSettings(_env_file=None, url="sqlite+aiosqlite:///:memory:")

        assert settings.url == "sqlite+aiosqlite:///:memory:"


class TestPromptSettingsDefaults:
    """Sprint 4, задача S4-06, ADR-4.4: бюджет `TokenBudgetPolicy` — из `Settings`, не хардкод."""

    def test_default_value(self) -> None:
        settings = PromptSettings(_env_file=None)

        assert settings.token_budget == 12000

    def test_loaded_from_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PROMPT_TOKEN_BUDGET", "500")

        settings = PromptSettings(_env_file=None)

        assert settings.token_budget == 500

    @pytest.mark.parametrize("invalid_budget", [0, -1, -1000])
    def test_non_positive_budget_raises_validation_error(
        self, monkeypatch: pytest.MonkeyPatch, invalid_budget: int
    ) -> None:
        monkeypatch.setenv("PROMPT_TOKEN_BUDGET", str(invalid_budget))

        with pytest.raises(ValidationError):
            PromptSettings(_env_file=None)


class TestModelCatalogSettingsDefaults:
    """Sprint 7, задача S7-03, ADR-7.4: путь к каталогу моделей — из `Settings`, не хардкод."""

    def test_default_catalog_path_points_at_seed_file_inside_package(self) -> None:
        settings = ModelCatalogSettings(_env_file=None)

        assert settings.catalog_path.name == "catalog.json"
        assert settings.catalog_path.exists()

    def test_loaded_from_environment(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        custom_path = tmp_path / "custom_catalog.json"
        monkeypatch.setenv("MODEL_CATALOG_CATALOG_PATH", str(custom_path))

        settings = ModelCatalogSettings(_env_file=None)

        assert settings.catalog_path == custom_path


class TestSecretsHaveNoDefaults:
    def test_telegram_settings_require_bot_token(self) -> None:
        with pytest.raises(ValidationError):
            TelegramSettings(_env_file=None)

    def test_llm_provider_settings_require_api_key(self) -> None:
        with pytest.raises(ValidationError):
            LLMProviderSettings(_env_file=None)


class TestSecretsAreNotExposed:
    def test_telegram_bot_token_not_shown_in_repr_or_str(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "super-secret-bot-token")
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "super-secret-webhook")

        settings = TelegramSettings(_env_file=None)

        assert "super-secret-bot-token" not in str(settings.bot_token)
        assert "super-secret-bot-token" not in repr(settings.bot_token)
        assert "super-secret-bot-token" not in str(settings)
        assert "super-secret-bot-token" not in repr(settings)
        # значение остаётся доступным явным вызовом, а не через str()/repr()
        assert settings.bot_token.get_secret_value() == "super-secret-bot-token"

    def test_llm_provider_api_key_not_shown_in_repr_or_str(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER_API_KEY", "super-secret-api-key")
        monkeypatch.setenv("LLM_PROVIDER_BASE_URL", "https://example-aggregator.test/v1")
        monkeypatch.setenv("LLM_PROVIDER_DEFAULT_MODEL", "test-model")

        settings = LLMProviderSettings(_env_file=None)

        assert "super-secret-api-key" not in str(settings)
        assert "super-secret-api-key" not in repr(settings)
        assert settings.api_key.get_secret_value() == "super-secret-api-key"


class TestSettingsAggregation:
    def test_settings_combines_all_groups(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "webhook-secret")
        monkeypatch.setenv("LLM_PROVIDER_API_KEY", "api-key")
        monkeypatch.setenv("LLM_PROVIDER_BASE_URL", "https://example-aggregator.test/v1")
        monkeypatch.setenv("LLM_PROVIDER_DEFAULT_MODEL", "test-model")
        monkeypatch.setenv("EMBEDDING_PROVIDER_API_KEY", "embedding-api-key")
        monkeypatch.setenv("EMBEDDING_PROVIDER_BASE_URL", "https://api.openai.com/v1")
        monkeypatch.setenv("ADMIN_API_KEY", "admin-api-key")
        monkeypatch.setenv("APP_PORT", "8080")
        monkeypatch.setenv("LLM_TEMPERATURE", "0.3")

        settings = Settings()

        assert isinstance(settings.application, ApplicationSettings)
        assert isinstance(settings.telegram, TelegramSettings)
        assert isinstance(settings.llm, LLMSettings)
        assert isinstance(settings.llm_provider, LLMProviderSettings)
        assert isinstance(settings.database, DatabaseSettings)
        assert isinstance(settings.prompt, PromptSettings)
        assert isinstance(settings.admin, AdminSettings)
        assert settings.application.port == 8080
        assert settings.llm.temperature == 0.3
        assert settings.telegram.bot_token.get_secret_value() == "token"
        assert settings.llm_provider.api_key.get_secret_value() == "api-key"
        assert settings.database.url == "sqlite+aiosqlite:///./data/app.db"
        assert settings.prompt.token_budget == 12000
        assert settings.admin.api_key.get_secret_value() == "admin-api-key"
