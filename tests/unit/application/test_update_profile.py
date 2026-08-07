"""
Тесты `UpdateProfile` (application/profile/use_cases/update_profile.py,
Sprint 8, задача S8-07, ADR-8.7/8.8).
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from tests.support.fake_conversation_repositories import (
    FakeProfileRepository,
    make_default_profile,
    make_in_memory_repositories_factory,
)

from dekoder.application.profile.dto import UpdateProfileCommand
from dekoder.application.profile.use_cases.update_profile import UpdateProfile
from dekoder.shared.logging import configure_logging


def _read_last_log_line(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "ожидалась хотя бы одна строка журнала"
    return json.loads(out[-1])


class TestUpdateProfileChangesOnlyProvidedFields:
    async def test_partial_update_changes_only_the_named_field(self) -> None:
        existing = make_default_profile(name="Исходный", is_default=False)
        profiles = FakeProfileRepository(profiles=[existing])
        use_case = UpdateProfile(repositories=make_in_memory_repositories_factory(profiles=profiles))

        result = await use_case.execute(UpdateProfileCommand(profile_id=existing.id, name="Изменённый"))

        assert result is not None
        assert result.name == "Изменённый"
        assert result.description == existing.description
        assert result.system_instruction == existing.system_instruction
        assert result.is_default == existing.is_default
        assert result.is_system == existing.is_system
        assert result.status == existing.status

    async def test_update_bumps_updated_at(self) -> None:
        existing = make_default_profile(is_default=False)
        profiles = FakeProfileRepository(profiles=[existing])
        use_case = UpdateProfile(repositories=make_in_memory_repositories_factory(profiles=profiles))

        result = await use_case.execute(UpdateProfileCommand(profile_id=existing.id, name="Новое имя"))

        assert result is not None
        assert result.updated_at >= existing.updated_at


class TestUpdateProfileUnknownId:
    async def test_returns_none_without_raising(self) -> None:
        use_case = UpdateProfile(repositories=make_in_memory_repositories_factory(profiles=FakeProfileRepository([])))

        result = await use_case.execute(UpdateProfileCommand(profile_id=uuid4(), name="x"))

        assert result is None


class TestUpdateProfileAuditLog:
    async def test_logs_update_event_with_profile_id_only(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        existing = make_default_profile(is_default=False)
        profiles = FakeProfileRepository(profiles=[existing])
        use_case = UpdateProfile(repositories=make_in_memory_repositories_factory(profiles=profiles))

        await use_case.execute(UpdateProfileCommand(profile_id=existing.id, name="Другое имя"))

        entry = _read_last_log_line(capsys)
        assert entry["event"] == "admin_profile_updated"
        assert entry["profile_id"] == str(existing.id)
        assert "name" not in entry
