"""
Тесты ListProfiles (application/profile/use_cases/list_profiles.py,
Sprint 3, задача S3-06).

Использует общий in-memory fake-helper `tests/support/
fake_conversation_repositories.py` (`FakeProfileRepository`, добавлен в
задаче S3-05) — без SQLAlchemy (backlog_2.md §9: «unit-тесты не должны
использовать SQLAlchemy»).
"""

from __future__ import annotations

import dataclasses

from tests.support.fake_conversation_repositories import (
    FakeProfileRepository,
    make_default_profile,
    make_in_memory_repositories_factory,
)

from dekoder.application.profile.use_cases.list_profiles import ListProfiles
from dekoder.domain.profile.entities import UserProfile
from dekoder.domain.profile.value_objects import ProfileStatus


class TestListProfiles:
    """AC-1: результат содержит все активные профили каталога."""

    async def test_returns_all_active_profiles_from_catalog(self) -> None:
        default_profile = make_default_profile(name="Деловой")
        expert_profile = make_default_profile(is_default=False, name="Экспертный")
        friendly_profile = make_default_profile(is_default=False, name="Дружелюбный")
        creative_profile = make_default_profile(is_default=False, name="Креативный")
        profiles = FakeProfileRepository([default_profile, expert_profile, friendly_profile, creative_profile])
        use_case = ListProfiles(repositories=make_in_memory_repositories_factory(profiles=profiles))

        result = await use_case.execute()

        assert {profile.name for profile in result.profiles} == {
            "Деловой",
            "Экспертный",
            "Дружелюбный",
            "Креативный",
        }
        assert len(result.profiles) == 4

    async def test_does_not_return_archived_profiles(self) -> None:
        active_profile = make_default_profile(name="Активный")
        archived_profile = _as_archived(make_default_profile(is_default=False, name="Архивный"))
        profiles = FakeProfileRepository([active_profile, archived_profile])
        use_case = ListProfiles(repositories=make_in_memory_repositories_factory(profiles=profiles))

        result = await use_case.execute()

        assert [profile.name for profile in result.profiles] == ["Активный"]


def _as_archived(profile: UserProfile) -> UserProfile:
    return dataclasses.replace(profile, status=ProfileStatus.ARCHIVED)
