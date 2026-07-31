"""
Тесты контракта UserRepository (application/user/ports.py, задача S2-03)
на fake-реализации (in-memory dict) — без обращения к SQLAlchemy/SQLite.
Стиль — как у `tests/unit/application/test_llm_provider_port.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from dekoder.application.user.ports import UserRepository
from dekoder.domain.user.entities import User


class FakeUserRepository:
    """Fake без наследования от UserRepository — Protocol допускает структурную типизацию."""

    def __init__(self) -> None:
        self._users_by_id: dict[UUID, User] = {}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._users_by_id.get(user_id)

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> User | None:
        for user in self._users_by_id.values():
            if user.telegram_user_id == telegram_user_id:
                return user
        return None

    async def save(self, user: User) -> User:
        self._users_by_id[user.id] = user
        return user

    async def get_or_create_by_telegram_user_id(self, telegram_user_id: int) -> User:
        existing = await self.get_by_telegram_user_id(telegram_user_id)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        new_user = User(id=uuid4(), telegram_user_id=telegram_user_id, created_at=now, updated_at=now)
        return await self.save(new_user)


def _make_user(telegram_user_id: int = 111) -> User:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    return User(id=uuid4(), telegram_user_id=telegram_user_id, created_at=now, updated_at=now)


class TestUserRepositoryPortIsFakeable:
    def test_fake_satisfies_the_protocol_structurally(self) -> None:
        fake = FakeUserRepository()

        assert isinstance(fake, UserRepository)


class TestGetById:
    async def test_returns_none_when_not_found(self) -> None:
        fake: UserRepository = FakeUserRepository()

        result = await fake.get_by_id(uuid4())

        assert result is None

    async def test_returns_saved_user(self) -> None:
        fake: UserRepository = FakeUserRepository()
        user = _make_user()
        await fake.save(user)

        result = await fake.get_by_id(user.id)

        assert result == user


class TestGetByTelegramUserId:
    async def test_returns_none_when_not_found(self) -> None:
        fake: UserRepository = FakeUserRepository()

        result = await fake.get_by_telegram_user_id(999)

        assert result is None

    async def test_returns_saved_user(self) -> None:
        fake: UserRepository = FakeUserRepository()
        user = _make_user(telegram_user_id=555)
        await fake.save(user)

        result = await fake.get_by_telegram_user_id(555)

        assert result == user


class TestSave:
    async def test_save_returns_the_saved_entity(self) -> None:
        fake: UserRepository = FakeUserRepository()
        user = _make_user()

        result = await fake.save(user)

        assert result == user
        assert await fake.get_by_id(user.id) == user


class TestGetOrCreateByTelegramUserId:
    async def test_creates_user_when_not_found(self) -> None:
        fake: UserRepository = FakeUserRepository()

        created = await fake.get_or_create_by_telegram_user_id(777)

        assert created.telegram_user_id == 777
        assert await fake.get_by_id(created.id) == created

    async def test_is_idempotent_for_repeated_calls(self) -> None:
        fake: UserRepository = FakeUserRepository()

        first = await fake.get_or_create_by_telegram_user_id(888)
        second = await fake.get_or_create_by_telegram_user_id(888)

        assert first.id == second.id
        assert first == second
