"""Тесты доменной сущности `Conversation` (domain/conversation/entities.py, задача S2-02)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from dekoder.domain.conversation.entities import Conversation


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _make_conversation(
    *,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    closed_at: datetime | None = None,
) -> Conversation:
    resolved_created_at = created_at if created_at is not None else _now()
    resolved_updated_at = updated_at if updated_at is not None else resolved_created_at
    return Conversation(
        id=uuid4(),
        user_id=uuid4(),
        created_at=resolved_created_at,
        updated_at=resolved_updated_at,
        closed_at=closed_at,
    )


class TestConversationCreation:
    def test_creates_active_conversation(self) -> None:
        conversation = _make_conversation()

        assert conversation.is_active is True
        assert conversation.closed_at is None

    def test_updated_at_before_created_at_is_rejected(self) -> None:
        created_at = _now()
        with pytest.raises(ValueError, match="updated_at"):
            _make_conversation(created_at=created_at, updated_at=created_at - timedelta(seconds=1))

    def test_closed_at_before_created_at_is_rejected_at_construction(self) -> None:
        created_at = _now()
        with pytest.raises(ValueError, match="closed_at"):
            _make_conversation(created_at=created_at, updated_at=created_at, closed_at=created_at - timedelta(days=1))

    def test_can_be_constructed_already_closed(self) -> None:
        created_at = _now()
        closed_at = created_at + timedelta(hours=1)

        conversation = _make_conversation(created_at=created_at, updated_at=closed_at, closed_at=closed_at)

        assert conversation.is_active is False


class TestConversationClose:
    def test_close_sets_closed_at_and_updates_updated_at(self) -> None:
        created_at = _now()
        conversation = _make_conversation(created_at=created_at, updated_at=created_at)
        closed_at = created_at + timedelta(minutes=10)

        conversation.close(closed_at)

        assert conversation.closed_at == closed_at
        assert conversation.updated_at == closed_at
        assert conversation.is_active is False

    def test_close_twice_is_rejected(self) -> None:
        created_at = _now()
        conversation = _make_conversation(created_at=created_at, updated_at=created_at)
        conversation.close(created_at + timedelta(minutes=1))

        with pytest.raises(ValueError, match="уже закрыт"):
            conversation.close(created_at + timedelta(minutes=2))

    def test_close_with_date_before_created_at_is_rejected(self) -> None:
        created_at = _now()
        conversation = _make_conversation(created_at=created_at, updated_at=created_at)

        with pytest.raises(ValueError, match="closed_at"):
            conversation.close(created_at - timedelta(seconds=1))

        # Отклонённая попытка закрытия не должна оставлять диалог частично изменённым.
        assert conversation.closed_at is None
        assert conversation.is_active is True

    def test_owner_is_not_part_of_close_signature(self) -> None:
        created_at = _now()
        conversation = _make_conversation(created_at=created_at, updated_at=created_at)
        original_user_id = conversation.user_id

        conversation.close(created_at + timedelta(minutes=1))

        assert conversation.user_id == original_user_id
