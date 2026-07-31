"""Тесты доменной сущности `User` (domain/user/entities.py, задача S2-02)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from dekoder.domain.user.entities import User


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


class TestUserCreation:
    def test_creates_valid_user(self) -> None:
        created_at = _now()
        user = User(
            id=uuid4(),
            telegram_user_id=123456789,
            created_at=created_at,
            updated_at=created_at,
        )

        assert user.telegram_user_id == 123456789
        assert user.created_at == created_at
        assert user.updated_at == created_at

    def test_updated_at_can_be_after_created_at(self) -> None:
        created_at = _now()
        updated_at = created_at + timedelta(minutes=5)

        user = User(id=uuid4(), telegram_user_id=1, created_at=created_at, updated_at=updated_at)

        assert user.updated_at == updated_at


class TestUserInvariants:
    def test_zero_telegram_user_id_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="telegram_user_id"):
            User(id=uuid4(), telegram_user_id=0, created_at=_now(), updated_at=_now())

    def test_negative_telegram_user_id_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="telegram_user_id"):
            User(id=uuid4(), telegram_user_id=-42, created_at=_now(), updated_at=_now())

    def test_updated_at_before_created_at_is_rejected(self) -> None:
        created_at = _now()
        updated_at = created_at - timedelta(seconds=1)

        with pytest.raises(ValueError, match="updated_at"):
            User(id=uuid4(), telegram_user_id=1, created_at=created_at, updated_at=updated_at)


class TestUserImmutability:
    def test_is_frozen(self) -> None:
        user = User(id=uuid4(), telegram_user_id=1, created_at=_now(), updated_at=_now())

        with pytest.raises(dataclasses.FrozenInstanceError):
            user.telegram_user_id = 2  # type: ignore[misc]
