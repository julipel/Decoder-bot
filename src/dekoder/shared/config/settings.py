"""
Конфигурация приложения (docs/versions/03, §4: "config/" под shared/).

Единственное место, где приложение читает переменные окружения. Адаптеры
и composition root получают значения из объекта Settings, а не обращаются
к os.environ самостоятельно (docs/versions/06, §13). Полный перечень
переменных и комментарии — в .env.example.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Telegram
    telegram_bot_token: str
    telegram_webhook_secret: str

    # Model Gateway — провайдеры генеративных моделей (docs/versions/02, §8)
    yandexgpt_api_key: str | None
    openai_api_key: str | None
    llm_provider: str
    llm_model: str
    embedding_provider: str
    embedding_model: str

    # Хранилища
    structured_storage_path: str
    vector_storage_url: str
    documents_storage_path: str
    audit_log_path: str

    # Author Profile Service (docs/versions/04, §8 — множественность)
    profile_active_limit: int
    profile_seed_path: str | None

    # Каталоги (seed-файлы в config/, docs/versions/03, §10)
    model_catalog_seed_path: str
    content_skill_seed_path: str

    # Memory Service
    dialogue_history_window_size: int
    fact_draft_ttl_seconds: int

    # Admin
    admin_login: str
    admin_password_hash: str
    admin_session_secret: str

    # Logging
    log_level: str


def load_settings() -> Settings:
    """Читает конфигурацию из переменных окружения. К внешним сервисам не обращается."""
    return Settings(
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_webhook_secret=os.environ.get("TELEGRAM_WEBHOOK_SECRET", ""),
        yandexgpt_api_key=os.environ.get("YANDEXGPT_API_KEY"),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        llm_provider=os.environ.get("LLM_PROVIDER", ""),
        llm_model=os.environ.get("LLM_MODEL", ""),
        embedding_provider=os.environ.get("EMBEDDING_PROVIDER", ""),
        embedding_model=os.environ.get("EMBEDDING_MODEL", ""),
        structured_storage_path=os.environ.get("STRUCTURED_STORAGE_PATH", ""),
        vector_storage_url=os.environ.get("VECTOR_STORAGE_URL", ""),
        documents_storage_path=os.environ.get("DOCUMENTS_STORAGE_PATH", ""),
        audit_log_path=os.environ.get("AUDIT_LOG_PATH", ""),
        profile_active_limit=int(os.environ.get("PROFILE_ACTIVE_LIMIT", "4")),
        profile_seed_path=os.environ.get("PROFILE_SEED_PATH"),
        model_catalog_seed_path=os.environ.get("MODEL_CATALOG_SEED_PATH", ""),
        content_skill_seed_path=os.environ.get("CONTENT_SKILL_SEED_PATH", ""),
        dialogue_history_window_size=int(os.environ.get("DIALOGUE_HISTORY_WINDOW_SIZE", "20")),
        fact_draft_ttl_seconds=int(os.environ.get("FACT_DRAFT_TTL_SECONDS", "300")),
        admin_login=os.environ.get("ADMIN_LOGIN", ""),
        admin_password_hash=os.environ.get("ADMIN_PASSWORD_HASH", ""),
        admin_session_secret=os.environ.get("ADMIN_SESSION_SECRET", ""),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
