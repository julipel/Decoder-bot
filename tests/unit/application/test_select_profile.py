"""
Тесты SelectProfile (application/profile/use_cases/select_profile.py,
Sprint 3, задача S3-06).

Использует общий in-memory fake-helper `tests/support/
fake_conversation_repositories.py` — без SQLAlchemy.
"""

from __future__ import annotations

from uuid import uuid4

from tests.support.fake_conversation_repositories import (
    FakeProfileRepository,
    FakeUserRepository,
    make_default_profile,
    make_in_memory_repositories_factory,
)

from dekoder.application.profile.dto import (
    GetActiveProfileCommand,
    SelectProfileCommand,
    SelectProfileStatus,
)
from dekoder.application.profile.use_cases.get_active_profile import GetActiveProfile
from dekoder.application.profile.use_cases.select_profile import SelectProfile


class TestUnknownUser:
    """AC: telegram_user_id, ни разу не писавший боту, -> UNKNOWN_USER."""

    async def test_returns_unknown_user_status(self) -> None:
        use_case = SelectProfile(repositories=make_in_memory_repositories_factory())

        result = await use_case.execute(SelectProfileCommand(telegram_user_id=999, profile_id=uuid4()))

        assert result.status is SelectProfileStatus.UNKNOWN_USER
        assert result.profile is None


class TestUnknownProfile:
    """AC-4: известный пользователь, отсутствующий в каталоге profile_id -> UNKNOWN_PROFILE, выбор не меняется."""

    async def test_returns_unknown_profile_status_without_changing_selection(self) -> None:
        users = FakeUserRepository()
        await users.get_or_create_by_telegram_user_id(111)
        default_profile = make_default_profile(name="Деловой")
        profiles = FakeProfileRepository([default_profile])
        repositories_factory = make_in_memory_repositories_factory(users=users, profiles=profiles)
        use_case = SelectProfile(repositories=repositories_factory)

        result = await use_case.execute(SelectProfileCommand(telegram_user_id=111, profile_id=uuid4()))

        assert result.status is SelectProfileStatus.UNKNOWN_PROFILE
        assert result.profile is None

        get_active_profile = GetActiveProfile(repositories=repositories_factory)
        active_result = await get_active_profile.execute(GetActiveProfileCommand(telegram_user_id=111))
        assert active_result.profile is not None
        assert active_result.profile.id == default_profile.id


class TestValidSelection:
    """AC-3: известный пользователь, валидный profile_id -> SELECTED, GetActiveProfile видит этот профиль."""

    async def test_selecting_valid_profile_updates_active_profile(self) -> None:
        users = FakeUserRepository()
        await users.get_or_create_by_telegram_user_id(222)
        default_profile = make_default_profile(name="Деловой")
        target_profile = make_default_profile(is_default=False, name="Экспертный")
        profiles = FakeProfileRepository([default_profile, target_profile])
        repositories_factory = make_in_memory_repositories_factory(users=users, profiles=profiles)
        use_case = SelectProfile(repositories=repositories_factory)

        result = await use_case.execute(SelectProfileCommand(telegram_user_id=222, profile_id=target_profile.id))

        assert result.status is SelectProfileStatus.SELECTED
        assert result.profile is not None
        assert result.profile.id == target_profile.id

        get_active_profile = GetActiveProfile(repositories=repositories_factory)
        active_result = await get_active_profile.execute(GetActiveProfileCommand(telegram_user_id=222))
        assert active_result.profile is not None
        assert active_result.profile.id == target_profile.id
