"""
Централизованная конфигурация приложения через pydantic-settings.

Единственное место, где приложение читает переменные окружения. Каждая
группа настроек — собственный `BaseSettings` со своим `env_prefix`, что
даёт понятные имена переменных (`TELEGRAM_BOT_TOKEN`, `LLM_TIMEOUT`, ...)
без вложенного разделителя. `Settings` объединяет группы полями с
`default_factory` — сама по себе не читает окружение напрямую, это делает
каждая вложенная группа при создании.

Секреты (`SecretStr`) не имеют значений по умолчанию — их отсутствие в
окружении обязано останавливать процесс на этапе создания `Settings()`
(fail-fast), а не проявляться позже как ошибка первого запроса.

`Settings()` не создаётся здесь на уровне модуля — единственная точка
создания настроек для реального запуска приложения — composition root
(`main.py` / `composition/`), что делает конфигурацию тестируемой без
переменных окружения процесса.
"""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env — буквальное имя из требований; .env.local — уже принятое в проекте
# соглашение для локальных значений разработчика (docs/versions/06, §6).
# Более поздний файл в списке переопределяет более ранний.
_ENV_FILES = (".env", ".env.local")


class ApplicationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=_ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    name: str = "dekoder"
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)


class TelegramSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_", env_file=_ENV_FILES, env_file_encoding="utf-8", extra="ignore"
    )

    bot_token: SecretStr
    webhook_secret: SecretStr


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_", env_file=_ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    timeout: float = Field(default=30.0, gt=0)
    max_tokens: int = Field(default=1024, gt=0)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class DatabaseSettings(BaseSettings):
    """
    Настройки постоянного хранилища данных (Sprint 2, S2-01). `url` —
    единственный источник строки подключения для SQLAlchemy async engine
    и Alembic (`infrastructure/persistence/engine.py`, `alembic/env.py`) —
    ни то, ни другое не читает `.env`/`os.getenv` самостоятельно.

    Значение по умолчанию — относительный путь (`./data/app.db`), не
    зависящий от абсолютного пути конкретной машины; переопределяется
    переменной окружения `DATABASE_URL` (в т.ч. в тестах, через
    `monkeypatch.setenv` или `_env_file=None` + явный `url=...`).
    """

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_", env_file=_ENV_FILES, env_file_encoding="utf-8", extra="ignore"
    )

    url: str = "sqlite+aiosqlite:///./data/app.db"


class OpenRouterSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPENROUTER_", env_file=_ENV_FILES, env_file_encoding="utf-8", extra="ignore"
    )

    api_key: SecretStr
    base_url: str = "https://openrouter.ai/api/v1"
    default_model: str = "openai/gpt-4o-mini"


class PromptSettings(BaseSettings):
    """
    Настройки Prompt Engine (Sprint 4, задача S4-06, ADR-4.4).

    `token_budget` — бюджет `TokenBudgetPolicy.enforce()`
    (`domain/prompt/policies.py`), в единицах эвристики оценки размера
    (`application/prompt/services/token_budget.py::estimate_size` —
    количество символов, не реальные токены модели, ADR-4.4). Значение
    по умолчанию (12000 символов) — намеренно консервативно относительно
    типичного контекстного окна моделей OpenRouter по умолчанию
    (десятки тысяч токенов) именно потому, что символы и токены не
    совпадают 1:1 (обычно 1 токен ≈ 3-4 символа для смешанного
    ru/en-текста) — это не точный расчёт, а осторожный запас.
    """

    model_config = SettingsConfigDict(
        env_prefix="PROMPT_", env_file=_ENV_FILES, env_file_encoding="utf-8", extra="ignore"
    )

    token_budget: int = Field(default=12000, gt=0)


class Settings(BaseSettings):
    """
    Корневой объект конфигурации — группирует настройки по областям.
    Не имеет собственного env_prefix: каждое вложенное поле читает
    переменные окружения самостоятельно, через свой BaseSettings.
    """

    model_config = SettingsConfigDict(env_file=_ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    application: ApplicationSettings = Field(default_factory=ApplicationSettings)
    # required SecretStr fields make TelegramSettings/OpenRouterSettings'
    # generated __init__ take required args from mypy's perspective, even
    # though pydantic-settings fills them from the environment at runtime.
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)  # type: ignore[arg-type]
    llm: LLMSettings = Field(default_factory=LLMSettings)
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings)  # type: ignore[arg-type]
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    prompt: PromptSettings = Field(default_factory=PromptSettings)
