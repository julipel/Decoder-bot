"""
Тесты `CreateProfile` (application/profile/use_cases/create_profile.py,
Sprint 8, задача S8-07, ADR-8.7/8.8).

Использует общий in-memory fake-helper `tests/support/
fake_conversation_repositories.py` — без SQLAlchemy. Тест логирования
перехватывает реальный JSON-вывод `shared/logging.py` через `capsys`, по
образцу `tests/unit/application/test_memory_use_cases.py`.
"""

from __future__ import annotations

import json

import pytest
from tests.support.fake_conversation_repositories import FakeProfileRepository, make_in_memory_repositories_factory

from dekoder.application.profile.dto import CreateProfileCommand
from dekoder.application.profile.use_cases.create_profile import CreateProfile
from dekoder.domain.profile.value_objects import ProfileStatus
from dekoder.shared.logging import configure_logging


def _read_last_log_line(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "ожидалась хотя бы одна строка журнала"
    return json.loads(out[-1])


def _make_command(**overrides: object) -> CreateProfileCommand:
    defaults: dict[str, object] = {
        "name": "Новый профиль",
        "description": "Описание",
        "system_instruction": "Инструкция",
        "response_style": "нейтральный",
        "target_audience": "все",
        "formality_level": "нейтральный",
        "preferred_structure": "без требований",
    }
    defaults.update(overrides)
    return CreateProfileCommand(**defaults)  # type: ignore[arg-type]


class TestCreateProfileAlwaysNonDefaultNonSystem:
    """AC-1: любой CreateProfileCommand -> результат с is_system=False, is_default=False."""

    async def test_created_profile_is_never_default_or_system(self) -> None:
        profiles = FakeProfileRepository(profiles=[])
        use_case = CreateProfile(repositories=make_in_memory_repositories_factory(profiles=profiles))

        result = await use_case.execute(_make_command())

        assert result.is_default is False
        assert result.is_system is False
        assert result.status is ProfileStatus.ACTIVE

    async def test_created_profile_is_persisted_and_retrievable(self) -> None:
        profiles = FakeProfileRepository(profiles=[])
        use_case = CreateProfile(repositories=make_in_memory_repositories_factory(profiles=profiles))

        result = await use_case.execute(_make_command(name="Профиль поддержки"))

        stored = await profiles.get_by_id(result.id)
        assert stored is not None
        assert stored.name == "Профиль поддержки"


class TestCreateProfileAuditLog:
    """AC-3: успешный CreateProfile логирует admin_profile_created с profile_id/name."""

    async def test_logs_creation_event(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        profiles = FakeProfileRepository(profiles=[])
        use_case = CreateProfile(repositories=make_in_memory_repositories_factory(profiles=profiles))

        result = await use_case.execute(_make_command(name="Аудит-тест"))

        entry = _read_last_log_line(capsys)
        assert entry["event"] == "admin_profile_created"
        assert entry["profile_id"] == str(result.id)
        assert entry["name"] == "Аудит-тест"
        # system_instruction (потенциально длинный/чувствительный текст) не логируется.
        assert "system_instruction" not in entry
