"""Тесты доменной сущности `KnowledgeDocument` (domain/knowledge/entities.py, задача S6-03)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from dekoder.domain.knowledge.entities import KnowledgeDocument
from dekoder.domain.knowledge.value_objects import DocumentStatus, DocumentType


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _make_document(**overrides: object) -> KnowledgeDocument:
    created_at = _now()
    defaults: dict[str, object] = {
        "id": uuid4(),
        "title": "Условия гарантии",
        "document_type": DocumentType.TXT,
        "source_filename": "warranty.txt",
        "checksum": "abc123",
        "status": DocumentStatus.UPLOADED,
        "tags": (),
        "description": None,
        "chunk_count": 0,
        "error_message": None,
        "created_at": created_at,
        "updated_at": created_at,
        "indexed_at": None,
    }
    defaults.update(overrides)
    return KnowledgeDocument(**defaults)  # type: ignore[arg-type]


class TestKnowledgeDocumentCreation:
    def test_creates_valid_document(self) -> None:
        document = _make_document()

        assert document.title == "Условия гарантии"
        assert document.status is DocumentStatus.UPLOADED
        assert document.chunk_count == 0

    def test_id_is_plain_uuid(self) -> None:
        document = _make_document()

        assert type(document.id) is UUID

    def test_indexed_at_defaults_to_none(self) -> None:
        document = _make_document()

        assert document.indexed_at is None

    def test_accepts_tags(self) -> None:
        document = _make_document(tags=("гарантия", "поддержка"))

        assert document.tags == ("гарантия", "поддержка")


class TestKnowledgeDocumentInvariants:
    def test_empty_title_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="title"):
            _make_document(title="")

    def test_blank_title_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="title"):
            _make_document(title="   ")

    def test_empty_checksum_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="checksum"):
            _make_document(checksum="")

    def test_negative_chunk_count_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="chunk_count"):
            _make_document(chunk_count=-1)

    def test_updated_at_before_created_at_is_rejected(self) -> None:
        created_at = _now()
        updated_at = created_at - timedelta(seconds=1)

        with pytest.raises(ValueError, match="updated_at"):
            _make_document(created_at=created_at, updated_at=updated_at)


class TestKnowledgeDocumentImmutability:
    def test_is_frozen(self) -> None:
        document = _make_document()

        with pytest.raises(dataclasses.FrozenInstanceError):
            document.title = "Другое"  # type: ignore[misc]


class TestKnowledgeEnumsArePlainEnum:
    """ADR-6.1: enum'ы — plain `Enum`, не `str, Enum` (стиль `MemoryCategory`/`ProfileStatus`)."""

    def test_document_type_is_not_str_subclass(self) -> None:
        assert not issubclass(DocumentType, str)

    def test_document_status_is_not_str_subclass(self) -> None:
        assert not issubclass(DocumentStatus, str)
