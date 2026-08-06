"""
Интеграционные тесты `SQLAlchemyKnowledgeDocumentRepository` (Sprint 6,
задача S6-04) на временной SQLite-базе (`tmp_path` — НЕ рабочая БД).
Стиль fixture'ов — как в `tests/integration/persistence/
test_memory_repository.py`. Без FK на `users` (в отличие от
`MemoryRecordORM`) — `knowledge_documents` не привязана к пользователю
(ADR-6.8: база знаний общая, не персональные данные).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from dekoder.domain.knowledge.entities import KnowledgeDocument
from dekoder.domain.knowledge.value_objects import DocumentStatus, DocumentType
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.knowledge_document_repository import SQLAlchemyKnowledgeDocumentRepository
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.shared.errors import InfrastructureError


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'knowledge-document-repository.db'}"
    test_engine = create_database_engine(database_url)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker:  # type: ignore[type-arg]
    return create_session_factory(engine)


def _make_document(**overrides: object) -> KnowledgeDocument:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    defaults: dict[str, object] = {
        "id": uuid4(),
        "title": "Условия гарантии",
        "document_type": DocumentType.TXT,
        "source_filename": "warranty.txt",
        "checksum": uuid4().hex,
        "status": DocumentStatus.UPLOADED,
        "tags": ("гарантия", "поддержка"),
        "description": "Документ об условиях гарантии.",
        "chunk_count": 0,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
        "indexed_at": None,
    }
    defaults.update(overrides)
    return KnowledgeDocument(**defaults)  # type: ignore[arg-type]


class TestSaveAndGetById:
    async def test_save_round_trips_all_fields_via_get_by_id(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        document = _make_document(tags=("a", "b"), description="desc")
        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            await repository.save(document)
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            fetched = await repository.get_by_id(document.id)

        assert fetched == document
        assert fetched is not None
        assert fetched.tags == ("a", "b")
        assert fetched.description == "desc"

    async def test_saving_duplicate_checksum_raises_infrastructure_error(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        """`ix_knowledge_documents_checksum` — уникальный индекс (ADR-6.9); нарушение не глотается молча."""
        first = _make_document(checksum="duplicate-checksum")
        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            await repository.save(first)
            await session.commit()

        second = _make_document(checksum="duplicate-checksum")
        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            with pytest.raises(InfrastructureError) as exc_info:
                await repository.save(second)

        assert exc_info.value.code == "KNOWLEDGE_DOCUMENT_SAVE_INTEGRITY_VIOLATION"

    async def test_get_by_id_returns_none_for_unknown_id(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            result = await repository.get_by_id(uuid4())

        assert result is None


class TestGetByChecksum:
    async def test_finds_document_with_matching_checksum(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        document = _make_document(checksum="deadbeef")
        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            await repository.save(document)
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            found = await repository.get_by_checksum("deadbeef")

        assert found is not None
        assert found.id == document.id

    async def test_returns_none_for_unknown_checksum(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            found = await repository.get_by_checksum("unknown")

        assert found is None


class TestUpdate:
    async def test_updates_status_chunk_count_and_indexed_at(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        document = _make_document(status=DocumentStatus.INDEXING)
        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            await repository.save(document)
            await session.commit()

        indexed_at = datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)
        updated_document = KnowledgeDocument(
            id=document.id,
            title=document.title,
            document_type=document.document_type,
            source_filename=document.source_filename,
            checksum=document.checksum,
            status=DocumentStatus.INDEXED,
            tags=document.tags,
            description=document.description,
            chunk_count=7,
            error_message=None,
            created_at=document.created_at,
            updated_at=document.updated_at,
            indexed_at=indexed_at,
        )
        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            updated = await repository.update(updated_document)
            await session.commit()

        assert updated.status is DocumentStatus.INDEXED
        assert updated.chunk_count == 7
        assert updated.indexed_at == indexed_at

        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            fetched = await repository.get_by_id(document.id)
        assert fetched is not None
        assert fetched.status is DocumentStatus.INDEXED
        assert fetched.chunk_count == 7

    async def test_raises_infrastructure_error_for_unknown_id(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            with pytest.raises(InfrastructureError):
                await repository.update(_make_document())


class TestDelete:
    async def test_delete_removes_the_document(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        document = _make_document()
        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            await repository.save(document)
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            await repository.delete(document.id)
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            assert await repository.get_by_id(document.id) is None

    async def test_delete_of_unknown_id_is_idempotent(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            repository = SQLAlchemyKnowledgeDocumentRepository(session)
            await repository.delete(uuid4())  # не должно поднимать исключение
            await session.commit()
