"""
Тесты `ListAllProfiles`
(application/profile/use_cases/list_all_profiles.py, Sprint 8, задача
S8-07, ADR-8.7).
"""

from __future__ import annotations

from dataclasses import replace

from tests.support.fake_conversation_repositories import (
    FakeProfileRepository,
    make_default_profile,
    make_in_memory_repositories_factory,
)

from dekoder.application.profile.use_cases.list_all_profiles import ListAllProfiles
from dekoder.domain.profile.value_objects import ProfileStatus


class TestListAllProfiles:
    async def test_returns_active_and_archived_profiles(self) -> None:
        active = make_default_profile(name="Активный", is_default=True)
        archived_source = make_default_profile(name="Архивный", is_default=False)
        archived = replace(archived_source, status=ProfileStatus.ARCHIVED)
        profiles = FakeProfileRepository(profiles=[active, archived])
        use_case = ListAllProfiles(repositories=make_in_memory_repositories_factory(profiles=profiles))

        result = await use_case.execute()

        assert {profile.id for profile in result.profiles} == {active.id, archived.id}
        statuses = {profile.status for profile in result.profiles}
        assert ProfileStatus.ACTIVE in statuses
        assert ProfileStatus.ARCHIVED in statuses

    async def test_empty_catalog_returns_empty_tuple(self) -> None:
        use_case = ListAllProfiles(repositories=make_in_memory_repositories_factory(profiles=FakeProfileRepository([])))

        result = await use_case.execute()

        assert result.profiles == ()
