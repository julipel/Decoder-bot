"""Тесты доменной сущности `UserProfile` (domain/profile/entities.py, задача S3-02)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.profile.entities import UserProfile
from dekoder.domain.profile.value_objects import ProfileStatus


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _make_profile(**overrides: object) -> UserProfile:
    created_at = _now()
    defaults: dict[str, object] = {
        "id": uuid4(),
        "name": "Деловой",
        "description": "Кратко и по делу, формальный стиль.",
        "system_instruction": "Отвечай кратко и по делу.",
        "response_style": "формальный",
        "target_audience": "широкая аудитория",
        "formality_level": "формальный",
        "preferred_structure": "выводы в начале",
        "forbidden_phrasing": (),
        "preferred_model": None,
        "response_length_hint": None,
        "additional_constraints": "",
        "status": ProfileStatus.ACTIVE,
        "is_system": True,
        "is_default": True,
        "created_at": created_at,
        "updated_at": created_at,
    }
    defaults.update(overrides)
    return UserProfile(**defaults)  # type: ignore[arg-type]


class TestUserProfileCreation:
    def test_creates_valid_profile(self) -> None:
        profile = _make_profile()

        assert profile.name == "Деловой"
        assert profile.status is ProfileStatus.ACTIVE
        assert profile.is_default is True

    def test_accepts_preferred_model(self) -> None:
        profile = _make_profile(preferred_model=ModelId("openai/gpt-4o-mini"))

        assert profile.preferred_model == ModelId("openai/gpt-4o-mini")

    def test_accepts_forbidden_phrasing_tuple(self) -> None:
        profile = _make_profile(forbidden_phrasing=("возможно", "наверное"))

        assert profile.forbidden_phrasing == ("возможно", "наверное")

    def test_updated_at_can_be_after_created_at(self) -> None:
        created_at = _now()
        updated_at = created_at + timedelta(minutes=5)

        profile = _make_profile(created_at=created_at, updated_at=updated_at)

        assert profile.updated_at == updated_at


class TestUserProfileInvariants:
    def test_empty_name_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="name"):
            _make_profile(name="")

    def test_blank_name_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="name"):
            _make_profile(name="   ")

    def test_empty_system_instruction_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="system_instruction"):
            _make_profile(system_instruction="")

    def test_blank_system_instruction_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="system_instruction"):
            _make_profile(system_instruction="   ")

    def test_updated_at_before_created_at_is_rejected(self) -> None:
        created_at = _now()
        updated_at = created_at - timedelta(seconds=1)

        with pytest.raises(ValueError, match="updated_at"):
            _make_profile(created_at=created_at, updated_at=updated_at)


class TestUserProfileImmutability:
    def test_is_frozen(self) -> None:
        profile = _make_profile()

        with pytest.raises(dataclasses.FrozenInstanceError):
            profile.name = "Другое"  # type: ignore[misc]
