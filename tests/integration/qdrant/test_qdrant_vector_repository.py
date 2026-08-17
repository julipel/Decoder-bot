"""
Интеграционные тесты `QdrantVectorRepository`/`ensure_collection`/
`build_qdrant_client` против настоящего Qdrant (Sprint 10, задача S10-01,
ADR-10.1) — впервые в проекте сетевые методы (`upsert_chunks`/`search`/
`delete_by_document`) проверяются не только вручную (докстринг Sprint 6,
`tests/unit/infrastructure/test_qdrant_vector_repository_helpers.py`), а
воспроизводимым автоматическим тестом. Требует `docker compose up -d
qdrant` — при недоступности `localhost:6333` весь модуль пропускается
(`qdrant_client` фикстура в `conftest.py`), не падает.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient

from dekoder.application.knowledge.pipeline import EmbeddedChunk
from dekoder.domain.knowledge.entities import KnowledgeDocument
from dekoder.domain.knowledge.value_objects import DocumentStatus, DocumentType
from dekoder.infrastructure.qdrant.client import ensure_collection
from dekoder.infrastructure.qdrant.vector_repository import QdrantVectorRepository
from dekoder.shared.config import QdrantSettings
from dekoder.shared.errors import InfrastructureError


def _make_document(**overrides: object) -> KnowledgeDocument:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    defaults: dict[str, object] = {
        "id": uuid4(),
        "title": "Условия гарантии",
        "document_type": DocumentType.TXT,
        "source_filename": "warranty.txt",
        "checksum": uuid4().hex,
        "status": DocumentStatus.INDEXED,
        "tags": ("гарантия", "поддержка"),
        "description": "Документ об условиях гарантии.",
        "chunk_count": 1,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
        "indexed_at": now,
    }
    defaults.update(overrides)
    return KnowledgeDocument(**defaults)  # type: ignore[arg-type]


def _make_chunk(text: str, vector: tuple[float, ...], chunk_index: int = 0) -> EmbeddedChunk:
    return EmbeddedChunk(
        chunk_index=chunk_index,
        text=text,
        page_number=None,
        section_title=None,
        vector=vector,
    )


class TestEnsureCollection:
    async def test_creates_collection_with_requested_dimension(
        self, qdrant_client: AsyncQdrantClient, qdrant_settings: QdrantSettings
    ) -> None:
        await ensure_collection(qdrant_client, qdrant_settings)

        exists = await qdrant_client.collection_exists(qdrant_settings.collection_name)
        assert exists is True
        info = await qdrant_client.get_collection(qdrant_settings.collection_name)
        assert info.config.params.vectors.size == qdrant_settings.vector_size  # type: ignore[union-attr]

    async def test_is_idempotent_on_repeated_call(
        self, qdrant_client: AsyncQdrantClient, qdrant_settings: QdrantSettings
    ) -> None:
        await ensure_collection(qdrant_client, qdrant_settings)
        await ensure_collection(qdrant_client, qdrant_settings)  # не должно поднять исключение

        exists = await qdrant_client.collection_exists(qdrant_settings.collection_name)
        assert exists is True


class TestUpsertAndSearchRoundtrip:
    async def test_search_finds_upserted_points_by_close_vector(
        self, qdrant_client: AsyncQdrantClient, qdrant_settings: QdrantSettings
    ) -> None:
        await ensure_collection(qdrant_client, qdrant_settings)
        repository = QdrantVectorRepository(qdrant_client, qdrant_settings.collection_name)
        document = _make_document()
        chunk = _make_chunk("Гарантия действует 24 месяца.", (1.0, 0.0, 0.0))

        await repository.upsert_chunks(document, [chunk])

        results = await repository.search((1.0, 0.0, 0.0), limit=5, min_score=0.0)

        assert len(results) == 1
        assert results[0].text == "Гарантия действует 24 месяца."
        assert results[0].source.document_id == document.id

    async def test_search_respects_limit_and_min_score(
        self, qdrant_client: AsyncQdrantClient, qdrant_settings: QdrantSettings
    ) -> None:
        await ensure_collection(qdrant_client, qdrant_settings)
        repository = QdrantVectorRepository(qdrant_client, qdrant_settings.collection_name)
        document = _make_document()
        chunks = [
            _make_chunk("Близкий фрагмент.", (1.0, 0.0, 0.0), chunk_index=0),
            _make_chunk("Дальний фрагмент.", (0.0, 1.0, 0.0), chunk_index=1),
        ]
        await repository.upsert_chunks(document, chunks)

        results = await repository.search((1.0, 0.0, 0.0), limit=1, min_score=0.0)
        assert len(results) == 1
        assert results[0].text == "Близкий фрагмент."

        results_high_threshold = await repository.search((1.0, 0.0, 0.0), limit=5, min_score=0.99)
        assert all(r.text == "Близкий фрагмент." for r in results_high_threshold)


class TestSearchFiltering:
    async def test_filters_by_document_ids(
        self, qdrant_client: AsyncQdrantClient, qdrant_settings: QdrantSettings
    ) -> None:
        await ensure_collection(qdrant_client, qdrant_settings)
        repository = QdrantVectorRepository(qdrant_client, qdrant_settings.collection_name)
        own_document = _make_document(title="Свой документ")
        other_document = _make_document(title="Чужой документ")
        await repository.upsert_chunks(own_document, [_make_chunk("Свой фрагмент.", (1.0, 0.0, 0.0))])
        await repository.upsert_chunks(other_document, [_make_chunk("Чужой фрагмент.", (1.0, 0.0, 0.0))])

        results = await repository.search((1.0, 0.0, 0.0), limit=10, min_score=0.0, document_ids=[own_document.id])

        assert len(results) == 1
        assert results[0].source.document_id == own_document.id

    async def test_filters_by_tags(self, qdrant_client: AsyncQdrantClient, qdrant_settings: QdrantSettings) -> None:
        await ensure_collection(qdrant_client, qdrant_settings)
        repository = QdrantVectorRepository(qdrant_client, qdrant_settings.collection_name)
        tagged_document = _make_document(title="С тегом", tags=("специальный",))
        untagged_document = _make_document(title="Без тега", tags=())
        await repository.upsert_chunks(tagged_document, [_make_chunk("Помеченный фрагмент.", (1.0, 0.0, 0.0))])
        await repository.upsert_chunks(untagged_document, [_make_chunk("Обычный фрагмент.", (1.0, 0.0, 0.0))])

        results = await repository.search((1.0, 0.0, 0.0), limit=10, min_score=0.0, tags=["специальный"])

        assert len(results) == 1
        assert results[0].source.document_id == tagged_document.id


class TestDeleteByDocument:
    async def test_deleted_points_are_not_found_afterwards(
        self, qdrant_client: AsyncQdrantClient, qdrant_settings: QdrantSettings
    ) -> None:
        await ensure_collection(qdrant_client, qdrant_settings)
        repository = QdrantVectorRepository(qdrant_client, qdrant_settings.collection_name)
        document = _make_document()
        await repository.upsert_chunks(document, [_make_chunk("Удаляемый фрагмент.", (1.0, 0.0, 0.0))])
        assert await repository.search((1.0, 0.0, 0.0), limit=5, min_score=0.0)

        await repository.delete_by_document(document.id)

        results = await repository.search((1.0, 0.0, 0.0), limit=5, min_score=0.0)
        assert results == []


class TestConnectionFailure:
    async def test_search_against_unreachable_host_raises_infrastructure_error(
        self, qdrant_settings: QdrantSettings
    ) -> None:
        unreachable_client = AsyncQdrantClient(host="localhost", port=1, timeout=1)
        repository = QdrantVectorRepository(unreachable_client, qdrant_settings.collection_name)

        with pytest.raises(InfrastructureError) as exc_info:
            await repository.search((1.0, 0.0, 0.0), limit=5, min_score=0.0)

        assert exc_info.value.code == "QDRANT_SEARCH_FAILED"
        await unreachable_client.close()

    async def test_upsert_against_unreachable_host_raises_infrastructure_error(
        self, qdrant_settings: QdrantSettings
    ) -> None:
        unreachable_client = AsyncQdrantClient(host="localhost", port=1, timeout=1)
        repository = QdrantVectorRepository(unreachable_client, qdrant_settings.collection_name)
        document = _make_document()

        with pytest.raises(InfrastructureError) as exc_info:
            await repository.upsert_chunks(document, [_make_chunk("Фрагмент.", (1.0, 0.0, 0.0))])

        assert exc_info.value.code == "QDRANT_UPSERT_FAILED"
        await unreachable_client.close()
