"""
Фикстуры интеграционного теста `QdrantVectorRepository` против настоящего
Qdrant (Sprint 10, задача S10-01, ADR-10.1). Требует запущенный
`docker compose up -d qdrant` (сервис уже существует с Sprint 6) — при
недоступности `localhost:6333` тест пропускается (`pytest.skip`), не падает,
чтобы не делать Docker обязательным условием остального прогона `pytest`.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator

import pytest
from qdrant_client import AsyncQdrantClient

from dekoder.infrastructure.qdrant.client import build_qdrant_client
from dekoder.shared.config import QdrantSettings


@pytest.fixture
def qdrant_settings() -> QdrantSettings:
    """Уникальное имя коллекции на запуск теста — не `dekoder_knowledge`, изоляция от прода/других прогонов."""
    return QdrantSettings(
        host="localhost",
        port=6333,
        collection_name=f"dekoder_test_{uuid.uuid4().hex[:12]}",
        vector_size=3,
    )


@pytest.fixture
async def qdrant_client(qdrant_settings: QdrantSettings) -> AsyncIterator[AsyncQdrantClient]:
    client = build_qdrant_client(qdrant_settings)
    try:
        await asyncio.wait_for(client.get_collections(), timeout=2.0)
    except Exception:
        await client.close()
        pytest.skip("Qdrant недоступен на localhost:6333 — запустите `docker compose up -d qdrant`")
    try:
        yield client
    finally:
        with contextlib.suppress(Exception):  # коллекция могла не быть создана в конкретном тесте
            await client.delete_collection(qdrant_settings.collection_name)
        await client.close()
