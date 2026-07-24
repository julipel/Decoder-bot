"""
Конфигурация приложения (модуль 10 — Configuration).

Единственное место, где приложение читает переменные окружения. Адаптеры
и composition root получают значения из объекта Settings, а не обращаются
к os.environ самостоятельно — это требование «конфигурация не должна быть
жёстко прописана в коде» (docs/02, §13). Полный перечень переменных и
комментарии — в .env.example.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Telegram
    telegram_bot_token: str
    telegram_webhook_secret: str

    # LLM Adapter (генеративная модель) — конфигурируется независимо от эмбеддингов
    llm_provider: str
    llm_model: str
    yandexgpt_api_key: str | None
    openai_api_key: str | None

    # Embedding Adapter (docs/02, §16.2) — независимая конфигурация
    embedding_provider: str
    embedding_model: str

    # Хранилища
    sqlite_path: str
    qdrant_url: str
    documents_storage_path: str

    # Профиль автора (docs/01, §2.3): единый профиль, seed при пустой БД
    profile_seed_path: str

    # Память (docs/02, §16.3, §16.5)
    dialogue_history_window_size: int
    fact_draft_ttl_seconds: int

    # Панель администратора (docs/01, §4.7; docs/02, §13)
    admin_login: str
    admin_password_hash: str
    admin_session_secret: str


def load_settings() -> Settings:
    """Читает конфигурацию из переменных окружения. К внешним сервисам не обращается."""
    return Settings(
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_webhook_secret=os.environ.get("TELEGRAM_WEBHOOK_SECRET", ""),
        llm_provider=os.environ.get("LLM_PROVIDER", ""),
        llm_model=os.environ.get("LLM_MODEL", ""),
        yandexgpt_api_key=os.environ.get("YANDEXGPT_API_KEY"),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        embedding_provider=os.environ.get("EMBEDDING_PROVIDER", ""),
        embedding_model=os.environ.get("EMBEDDING_MODEL", ""),
        sqlite_path=os.environ.get("SQLITE_PATH", ""),
        qdrant_url=os.environ.get("QDRANT_URL", ""),
        documents_storage_path=os.environ.get("DOCUMENTS_STORAGE_PATH", ""),
        profile_seed_path=os.environ.get("PROFILE_SEED_PATH", ""),
        dialogue_history_window_size=int(os.environ.get("DIALOGUE_HISTORY_WINDOW_SIZE", "20")),
        fact_draft_ttl_seconds=int(os.environ.get("FACT_DRAFT_TTL_SECONDS", "300")),
        admin_login=os.environ.get("ADMIN_LOGIN", ""),
        admin_password_hash=os.environ.get("ADMIN_PASSWORD_HASH", ""),
        admin_session_secret=os.environ.get("ADMIN_SESSION_SECRET", ""),
    )
