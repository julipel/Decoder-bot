"""
Тесты StartNewConversation (application/conversation/use_cases/start_new_conversation.py, Sprint 2, задача S2-07).

Использует общий in-memory fake-helper `tests/support/fake_conversation_repositories.py`
(тот же, что и тесты `ProcessUserMessage`, задача S2-06) — без SQLAlchemy
(backlog_2.md §9: «unit-тесты не должны использовать SQLAlchemy»).
Интеграционный тест на реальном persistence-потоке —
tests/integration/test_start_new_conversation_persistence.py.
"""

from __future__ import annotations

from tests.support.fake_conversation_repositories import (
    FakeConversationRepository,
    FakeUserRepository,
    make_in_memory_repositories_factory,
)

from dekoder.application.conversation.dto import StartNewConversationCommand
from dekoder.application.conversation.use_cases.start_new_conversation import StartNewConversation
from dekoder.domain.user.entities import User
from dekoder.shared.domain.identifiers import CorrelationId


def _make_command(telegram_user_id: int = 123) -> StartNewConversationCommand:
    return StartNewConversationCommand(telegram_user_id=telegram_user_id, correlation_id=CorrelationId("corr-1"))


def _make_use_case(
    users: FakeUserRepository | None = None,
    conversations: FakeConversationRepository | None = None,
) -> tuple[StartNewConversation, FakeUserRepository, FakeConversationRepository]:
    users = users if users is not None else FakeUserRepository()
    conversations = conversations if conversations is not None else FakeConversationRepository()
    factory = make_in_memory_repositories_factory(users=users, conversations=conversations)
    return StartNewConversation(repositories=factory), users, conversations


async def _seed_user(users: FakeUserRepository, telegram_user_id: int) -> User:
    return await users.get_or_create_by_telegram_user_id(telegram_user_id)


class TestMissingUser:
    """Обязательный сценарий: пользователь отсутствует."""

    async def test_returns_successful_result_without_conversation_id(self) -> None:
        use_case, _, _ = _make_use_case()

        result = await use_case.execute(_make_command(telegram_user_id=999))

        assert result.conversation_id is None

    async def test_does_not_create_user(self) -> None:
        use_case, users, _ = _make_use_case()

        await use_case.execute(_make_command(telegram_user_id=999))

        assert await users.get_by_telegram_user_id(999) is None


class TestNoActiveConversation:
    """Обязательный сценарий: у существующего пользователя нет активного диалога — создаётся новый напрямую."""

    async def test_creates_new_conversation_directly_without_closing_anything(self) -> None:
        users = FakeUserRepository()
        user = await _seed_user(users, telegram_user_id=42)
        use_case, _, conversations = _make_use_case(users=users)

        result = await use_case.execute(_make_command(telegram_user_id=42))

        assert result.conversation_id is not None
        stored = await conversations.get_by_id(result.conversation_id)
        assert stored is not None
        assert stored.user_id == user.id
        assert stored.is_active
        assert stored.closed_at is None


class TestActiveConversationExists:
    """Обязательный сценарий: активный диалог существует — закрывается через доменную модель, создаётся новый."""

    async def test_closes_previous_conversation_through_domain_method(self) -> None:
        users = FakeUserRepository()
        user = await _seed_user(users, telegram_user_id=7)
        conversations = FakeConversationRepository()
        previous = await conversations.get_or_create_active(user.id)
        use_case, _, _ = _make_use_case(users=users, conversations=conversations)

        await use_case.execute(_make_command(telegram_user_id=7))

        stored_previous = await conversations.get_by_id(previous.id)
        assert stored_previous is not None
        assert not stored_previous.is_active
        assert stored_previous.closed_at is not None

    async def test_new_conversation_has_different_id_and_is_active(self) -> None:
        users = FakeUserRepository()
        user = await _seed_user(users, telegram_user_id=7)
        conversations = FakeConversationRepository()
        previous = await conversations.get_or_create_active(user.id)
        use_case, _, _ = _make_use_case(users=users, conversations=conversations)

        result = await use_case.execute(_make_command(telegram_user_id=7))

        assert result.conversation_id is not None
        assert result.conversation_id != previous.id
        new_conversation = await conversations.get_by_id(result.conversation_id)
        assert new_conversation is not None
        assert new_conversation.is_active

    async def test_new_conversation_becomes_the_only_active_one(self) -> None:
        users = FakeUserRepository()
        user = await _seed_user(users, telegram_user_id=7)
        conversations = FakeConversationRepository()
        await conversations.get_or_create_active(user.id)
        use_case, _, _ = _make_use_case(users=users, conversations=conversations)

        result = await use_case.execute(_make_command(telegram_user_id=7))

        active = await conversations.get_active_by_user_id(user.id)
        assert active is not None
        assert active.id == result.conversation_id


class TestRepeatedCalls:
    """Обязательный сценарий: повторный вызов создаёт ещё один новый диалог; старые не удаляются."""

    async def test_second_call_creates_another_new_conversation_with_different_id(self) -> None:
        users = FakeUserRepository()
        await _seed_user(users, telegram_user_id=55)
        conversations = FakeConversationRepository()
        use_case, _, _ = _make_use_case(users=users, conversations=conversations)

        first_result = await use_case.execute(_make_command(telegram_user_id=55))
        second_result = await use_case.execute(_make_command(telegram_user_id=55))

        assert first_result.conversation_id is not None
        assert second_result.conversation_id is not None
        assert first_result.conversation_id != second_result.conversation_id

    async def test_old_conversations_are_not_deleted(self) -> None:
        users = FakeUserRepository()
        user = await _seed_user(users, telegram_user_id=55)
        conversations = FakeConversationRepository()
        use_case, _, _ = _make_use_case(users=users, conversations=conversations)

        first_result = await use_case.execute(_make_command(telegram_user_id=55))
        second_result = await use_case.execute(_make_command(telegram_user_id=55))
        third_result = await use_case.execute(_make_command(telegram_user_id=55))
        assert first_result.conversation_id is not None
        assert second_result.conversation_id is not None
        assert third_result.conversation_id is not None

        assert await conversations.get_by_id(first_result.conversation_id) is not None
        assert await conversations.get_by_id(second_result.conversation_id) is not None
        assert await conversations.get_by_id(third_result.conversation_id) is not None

        only_active = await conversations.get_active_by_user_id(user.id)
        assert only_active is not None
        assert only_active.id == third_result.conversation_id
