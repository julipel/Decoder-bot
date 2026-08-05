"""Тесты доменной сущности `MemoryRecord` (domain/memory/entities.py, задача S5-02)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import (
    MemoryCategory,
    MemoryConfidence,
    MemorySource,
    MemoryStatus,
)


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _make_record(**overrides: object) -> MemoryRecord:
    created_at = _now()
    defaults: dict[str, object] = {
        "id": uuid4(),
        "user_id": uuid4(),
        "text": "Работает Python-разработчиком.",
        "category": MemoryCategory.FACT,
        "source": MemorySource.USER_EXPLICIT,
        "status": MemoryStatus.CONFIRMED,
        "confidence": MemoryConfidence.MEDIUM,
        "is_sensitive": False,
        "expires_at": None,
        "updated_by": "user",
        "created_at": created_at,
        "updated_at": created_at,
    }
    defaults.update(overrides)
    return MemoryRecord(**defaults)  # type: ignore[arg-type]


class TestMemoryRecordCreation:
    def test_creates_valid_record(self) -> None:
        record = _make_record()

        assert record.text == "Работает Python-разработчиком."
        assert record.status is MemoryStatus.CONFIRMED
        assert record.is_sensitive is False

    def test_id_and_user_id_are_plain_uuid(self) -> None:
        record = _make_record()

        assert type(record.id) is UUID
        assert type(record.user_id) is UUID

    def test_accepts_expires_at(self) -> None:
        expires_at = _now() + timedelta(days=30)

        record = _make_record(expires_at=expires_at)

        assert record.expires_at == expires_at

    def test_updated_at_can_be_after_created_at(self) -> None:
        created_at = _now()
        updated_at = created_at + timedelta(minutes=5)

        record = _make_record(created_at=created_at, updated_at=updated_at)

        assert record.updated_at == updated_at

    def test_accepts_sensitive_flag(self) -> None:
        record = _make_record(is_sensitive=True)

        assert record.is_sensitive is True


class TestMemoryRecordInvariants:
    def test_empty_text_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="text"):
            _make_record(text="")

    def test_blank_text_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="text"):
            _make_record(text="   ")

    def test_updated_at_before_created_at_is_rejected(self) -> None:
        created_at = _now()
        updated_at = created_at - timedelta(seconds=1)

        with pytest.raises(ValueError, match="updated_at"):
            _make_record(created_at=created_at, updated_at=updated_at)


class TestMemoryRecordImmutability:
    def test_is_frozen(self) -> None:
        record = _make_record()

        with pytest.raises(dataclasses.FrozenInstanceError):
            record.text = "Другое"  # type: ignore[misc]


class TestMemoryEnumsArePlainEnum:
    """ADR-5.3: enum'ы — plain `Enum`, не `str, Enum` (стиль `ProfileStatus`)."""

    def test_memory_category_is_not_str_subclass(self) -> None:
        assert not issubclass(MemoryCategory, str)

    def test_memory_source_is_not_str_subclass(self) -> None:
        assert not issubclass(MemorySource, str)

    def test_memory_status_is_not_str_subclass(self) -> None:
        assert not issubclass(MemoryStatus, str)

    def test_memory_confidence_is_not_str_subclass(self) -> None:
        assert not issubclass(MemoryConfidence, str)
