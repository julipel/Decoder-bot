"""
Тесты `DeactivateProfile`
(application/profile/use_cases/deactivate_profile.py, Sprint 8, задача
S8-07, ADR-8.7/8.8).
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

from dekoder.application.profile.dto import DeactivateProfileCommand, DeactivateProfileStatus
from dekoder.application.profile.use_cases.deactivate_profile import DeactivateProfile
from dekoder.domain.profile.value_objects import ProfileStatus
from dekoder.shared.errors import ApplicationError
from dekoder.shared.logging import configure_logging


def _read_last_log_line(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "ожидалась хотя бы одна строка журнала"
    return json.loads(out[-1])


class TestDeactivateProfileRejectsDefault:
    """AC-2: профиль с is_default=True -> ApplicationError(PROFILE_ARCHIVE_DEFAULT_FORBIDDEN), status не меняется."""

    async def test_raises_and_does_not_change_status(self) -> None:
        default_profile = make_default_profile(is_default=True)
        profiles = FakeProfileRepository(profiles=[default_profile])
        use_case = DeactivateProfile(repositories=make_in_memory_repositories_factory(profiles=profiles))

        with pytest.raises(ApplicationError) as exc_info:
            await use_case.execute(DeactivateProfileCommand(profile_id=default_profile.id))

        assert exc_info.value.code == "PROFILE_ARCHIVE_DEFAULT_FORBIDDEN"
        stored = await profiles.get_by_id(default_profile.id)
        assert stored is not None
        assert stored.status is ProfileStatus.ACTIVE


class TestDeactivateProfileArchivesNonDefault:
    async def test_archives_a_regular_profile(self) -> None:
        profile = make_default_profile(is_default=False)
        profiles = FakeProfileRepository(profiles=[profile])
        use_case = DeactivateProfile(repositories=make_in_memory_repositories_factory(profiles=profiles))

        result = await use_case.execute(DeactivateProfileCommand(profile_id=profile.id))

        assert result.status is DeactivateProfileStatus.ARCHIVED
        assert result.profile is not None
        assert result.profile.status is ProfileStatus.ARCHIVED


class TestDeactivateProfileUnknownId:
    async def test_returns_unknown_profile_status(self) -> None:
        use_case = DeactivateProfile(
            repositories=make_in_memory_repositories_factory(profiles=FakeProfileRepository([]))
        )

        result = await use_case.execute(DeactivateProfileCommand(profile_id=uuid4()))

        assert result.status is DeactivateProfileStatus.UNKNOWN_PROFILE
        assert result.profile is None


class TestDeactivateProfileAuditLog:
    async def test_logs_archived_event(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        profile = make_default_profile(is_default=False)
        profiles = FakeProfileRepository(profiles=[profile])
        use_case = DeactivateProfile(repositories=make_in_memory_repositories_factory(profiles=profiles))

        await use_case.execute(DeactivateProfileCommand(profile_id=profile.id))

        entry = _read_last_log_line(capsys)
        assert entry["event"] == "admin_profile_archived"
        assert entry["profile_id"] == str(profile.id)
