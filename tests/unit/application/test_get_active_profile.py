"""
Тесты GetActiveProfile (application/profile/use_cases/
get_active_profile.py, Sprint 3, задача S3-06).

Использует общий in-memory fake-helper `tests/support/
fake_conversation_repositories.py` — без SQLAlchemy.
"""

from __future__ import annotations

from tests.support.fake_conversation_repositories import (
    FakeProfileRepository,
    FakeUserRepository,
    make_default_profile,
    make_in_memory_repositories_factory,
)

from dekoder.application.profile.dto import GetActiveProfileCommand
from dekoder.application.profile.use_cases.get_active_profile import GetActiveProfile


class TestUnknownUser:
    """AC-2: telegram_user_id, ни разу не писавший боту, -> profile is None."""

    async def test_returns_none_profile_for_unknown_user(self) -> None:
        use_case = GetActiveProfile(repositories=make_in_memory_repositories_factory())

        result = await use_case.execute(GetActiveProfileCommand(telegram_user_id=999))

        assert result.profile is None


class TestKnownUserWithoutExplicitSelection:
    async def test_returns_default_profile(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(123)
        default_profile = make_default_profile(name="Деловой")
        profiles = FakeProfileRepository([default_profile])
        use_case = GetActiveProfile(repositories=make_in_memory_repositories_factory(users=users, profiles=profiles))

        result = await use_case.execute(GetActiveProfileCommand(telegram_user_id=123))

        assert result.profile is not None
        assert result.profile.id == default_profile.id
        assert user.telegram_user_id == 123


class TestKnownUserWithExplicitSelection:
    async def test_returns_previously_selected_profile(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(456)
        default_profile = make_default_profile(name="Деловой")
        other_profile = make_default_profile(is_default=False, name="Экспертный")
        profiles = FakeProfileRepository([default_profile, other_profile])
        await profiles.select_profile(user.id, other_profile.id)
        use_case = GetActiveProfile(repositories=make_in_memory_repositories_factory(users=users, profiles=profiles))

        result = await use_case.execute(GetActiveProfileCommand(telegram_user_id=456))

        assert result.profile is not None
        assert result.profile.id == other_profile.id
