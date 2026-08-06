"""
Подключение к Qdrant — bootstrap-уровень инфраструктуры (Sprint 6, задача
S6-02, Этап 8 «Плана реализации.md»).

`build_qdrant_client`/`ensure_collection` — тот же приём, что и
`bootstrap/database.py::init_database` для SQLite: единая точка создания
клиента и явная проверка готовности хранилища (здесь — существование
коллекции с нужной размерностью вектора) до того, как приложение начнёт
принимать трафик, вместо того чтобы обнаружить проблему позже как ошибку
первого запроса поиска/индексации.

`QdrantVectorRepository` (`infrastructure/qdrant/vector_repository.py`,
задача S6-05) получает уже созданный `AsyncQdrantClient` через конструктор
и не отвечает за его подключение/закрытие — тем же приёмом, что
`OpenRouterLLMAdapter` получает `httpx.AsyncClient`.
"""

from __future__ import annotations

from qdrant_client import AsyncQdrantClient, models

from dekoder.shared.config import QdrantSettings
from dekoder.shared.errors import InfrastructureError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


def build_qdrant_client(settings: QdrantSettings) -> AsyncQdrantClient:
    """Создаёт клиент Qdrant поверх REST (`host`/`port`) — без gRPC, по стилю остальных HTTP-адаптеров проекта."""
    return AsyncQdrantClient(host=settings.host, port=settings.port)


async def ensure_collection(client: AsyncQdrantClient, settings: QdrantSettings) -> None:
    """
    Создаёт коллекцию `settings.collection_name`, если её ещё нет —
    идемпотентно, безопасно вызывать при каждом старте приложения (как и
    `init_database`, не только один раз вручную). Не проверяет и не
    исправляет размерность вектора уже существующей коллекции: смена
    `QDRANT_VECTOR_SIZE`/модели эмбеддингов на уже проиндексированном
    корпусе — операционное решение (пересоздать коллекцию/переиндексировать
    документы), не то, что должно происходить неявно при старте процесса.
    """
    try:
        exists = await client.collection_exists(settings.collection_name)
        if exists:
            # Обнаружено при собственном запуске docker compose (задача
            # S6-11): без этой строки второй процесс (api и telegram-bot
            # проверяют коллекцию независимо и почти одновременно при
            # старте) молча завершает `ensure_collection` без единого
            # лога — со стороны выглядит неотличимо от зависшего вызова.
            _logger.info("qdrant_collection_already_exists", collection_name=settings.collection_name)
            return
        await client.create_collection(
            collection_name=settings.collection_name,
            vectors_config=models.VectorParams(size=settings.vector_size, distance=models.Distance.COSINE),
        )
        _logger.info(
            "qdrant_collection_created",
            collection_name=settings.collection_name,
            vector_size=settings.vector_size,
        )
    except Exception as exc:  # любой сбой подключения/создания превращается в понятную InfrastructureError ниже
        _logger.error("qdrant_collection_setup_failed", error=str(exc))
        raise InfrastructureError(
            message=f"Не удалось подготовить коллекцию Qdrant '{settings.collection_name}': {exc}",
            user_message="Не удалось подготовить хранилище базы знаний.",
            code="QDRANT_COLLECTION_SETUP_FAILED",
            cause=exc,
        ) from exc
