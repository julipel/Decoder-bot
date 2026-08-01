"""
Тесты ClearConversation (application/conversation/use_cases/clear_conversation.py, Sprint 2, задача S2-09).

Использует общий in-memory fake-helper `tests/support/fake_conversation_repositories.py`
(тот же, что и тесты `ProcessUserMessage`/`StartNewConversation`) — без
SQLAlchemy (backlog_2.md §9: «unit-тесты не должны использовать
SQLAlchemy»). Интеграционный тест на реальном persistence-потоке —
tests/integration/test_clear_conversation_persistence.py.

`SpyConversationRepository`/`SpyMessageRepository` оборачивают
соответствующие fake-репозитории и считают вызовы методов — нужно, чтобы
доказать не только результирующее состояние («диалог не закрыт»), но и
факт отсутствия вызова («`.close()`/`.save()` не вызваны ни разу»,
«`.clear()` вызван ровно один раз и с верным `conversation_id`»).
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from uuid import UUID, uuid4

from tests.support.fake_conversation_repositories import (
    FakeConversationRepository,
    FakeMessageRepository,
    FakeUserRepository,
    make_in_memory_repositories_factory,
)

from dekoder.application.conversation.dto import ClearConversationCommand, ClearConversationStatus
from dekoder.application.conversation.use_cases.clear_conversation import ClearConversation
from dekoder.domain.conversation.entities import Conversation, Message, MessageRole
from dekoder.domain.user.entities import User


class SpyConversationRepository:
    """Оборачивает `FakeConversationRepository`, считая вызовы `save()`/`close()`."""

    def __init__(self, inner: FakeConversationRepository) -> None:
        self._inner = inner
        self.save_calls = 0
        self.close_calls = 0

    async def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        return await self._inner.get_by_id(conversation_id)

    async def get_active_by_user_id(self, user_id: UUID) -> Conversation | None:
        return await self._inner.get_active_by_user_id(user_id)

    async def save(self, conversation: Conversation) -> Conversation:
        self.save_calls += 1
        return await self._inner.save(conversation)

    async def close(self, conversation: Conversation) -> Conversation:
        self.close_calls += 1
        return await self._inner.close(conversation)

    async def get_or_create_active(self, user_id: UUID) -> Conversation:
        return await self._inner.get_or_create_active(user_id)


class SpyMessageRepository:
    """Оборачивает `FakeMessageRepository`, считая вызовы `clear()` и запоминая аргументы."""

    def __init__(self, inner: FakeMessageRepository) -> None:
        self._inner = inner
        self.clear_calls: list[UUID] = []

    async def save(self, message: Message) -> Message:
        return await self._inner.save(message)

    async def history(self, conversation_id: UUID) -> list[Message]:
        return await self._inner.history(conversation_id)

    async def clear(self, conversation_id: UUID) -> int:
        self.clear_calls.append(conversation_id)
        return await self._inner.clear(conversation_id)


def _make_command(telegram_user_id: int = 123) -> ClearConversationCommand:
    return ClearConversationCommand(telegram_user_id=telegram_user_id)


def _make_use_case(
    users: FakeUserRepository | None = None,
    conversations: SpyConversationRepository | None = None,
    messages: SpyMessageRepository | None = None,
) -> tuple[ClearConversation, FakeUserRepository, SpyConversationRepository, SpyMessageRepository]:
    users = users if users is not None else FakeUserRepository()
    conversations = (
        conversations if conversations is not None else SpyConversationRepository(FakeConversationRepository())
    )
    messages = messages if messages is not None else SpyMessageRepository(FakeMessageRepository())
    factory = make_in_memory_repositories_factory(
        users=users,
        conversations=conversations,  # type: ignore[arg-type]
        messages=messages,  # type: ignore[arg-type]
    )
    return ClearConversation(repositories=factory), users, conversations, messages


async def _seed_user(users: FakeUserRepository, telegram_user_id: int) -> User:
    return await users.get_or_create_by_telegram_user_id(telegram_user_id)


def _seed_message(conversation_id: UUID, role: MessageRole = MessageRole.USER, content: str = "hi") -> Message:
    return Message(
        id=uuid4(), conversation_id=conversation_id, role=role, content=content, created_at=datetime.now(UTC)
    )


class TestMissingUser:
    """Обязательный сценарий: пользователь отсутствует."""

    async def test_returns_no_active_conversation_status(self) -> None:
        use_case, _, _, _ = _make_use_case()

        result = await use_case.execute(_make_command(telegram_user_id=999))

        assert result.status == ClearConversationStatus.NO_ACTIVE_CONVERSATION
        assert result.conversation_id is None
        assert result.deleted_count == 0

    async def test_does_not_create_user(self) -> None:
        use_case, users, _, _ = _make_use_case()

        await use_case.execute(_make_command(telegram_user_id=999))

        assert await users.get_by_telegram_user_id(999) is None

    async def test_does_not_call_messages_clear(self) -> None:
        use_case, _, _, messages = _make_use_case()

        await use_case.execute(_make_command(telegram_user_id=999))

        assert messages.clear_calls == []


class TestNoActiveConversation:
    """Обязательный сценарий: пользователь существует, но активного диалога нет."""

    async def test_returns_no_active_conversation_status(self) -> None:
        users = FakeUserRepository()
        await _seed_user(users, telegram_user_id=42)
        use_case, _, _, _ = _make_use_case(users=users)

        result = await use_case.execute(_make_command(telegram_user_id=42))

        assert result.status == ClearConversationStatus.NO_ACTIVE_CONVERSATION
        assert result.conversation_id is None
        assert result.deleted_count == 0

    async def test_does_not_create_conversation(self) -> None:
        users = FakeUserRepository()
        user = await _seed_user(users, telegram_user_id=42)
        use_case, _, conversations, _ = _make_use_case(users=users)

        await use_case.execute(_make_command(telegram_user_id=42))

        assert await conversations.get_active_by_user_id(user.id) is None
        assert conversations.save_calls == 0

    async def test_does_not_call_messages_clear(self) -> None:
        users = FakeUserRepository()
        await _seed_user(users, telegram_user_id=42)
        use_case, _, _, messages = _make_use_case(users=users)

        await use_case.execute(_make_command(telegram_user_id=42))

        assert messages.clear_calls == []


class TestActiveConversationWithMessages:
    """Обязательный сценарий: активный диалог существует и содержит сообщения — история очищается."""

    async def test_clears_history_and_returns_cleared_status(self) -> None:
        users = FakeUserRepository()
        user = await _seed_user(users, telegram_user_id=7)
        conversations = SpyConversationRepository(FakeConversationRepository())
        active = await conversations.get_or_create_active(user.id)
        messages_inner = FakeMessageRepository()
        await messages_inner.save(_seed_message(active.id))
        await messages_inner.save(_seed_message(active.id))
        messages = SpyMessageRepository(messages_inner)
        use_case, _, _, _ = _make_use_case(users=users, conversations=conversations, messages=messages)

        result = await use_case.execute(_make_command(telegram_user_id=7))

        assert result.status == ClearConversationStatus.CLEARED
        assert result.conversation_id == active.id
        assert result.deleted_count == 2
        assert await messages.history(active.id) == []

    async def test_calls_messages_clear_with_correct_conversation_id(self) -> None:
        users = FakeUserRepository()
        user = await _seed_user(users, telegram_user_id=7)
        conversations = SpyConversationRepository(FakeConversationRepository())
        active = await conversations.get_or_create_active(user.id)
        messages_inner = FakeMessageRepository()
        await messages_inner.save(_seed_message(active.id))
        messages = SpyMessageRepository(messages_inner)
        use_case, _, _, _ = _make_use_case(users=users, conversations=conversations, messages=messages)

        await use_case.execute(_make_command(telegram_user_id=7))

        assert messages.clear_calls == [active.id]


class TestActiveConversationAlreadyEmpty:
    """Обязательный сценарий: диалог активен, история уже пуста — отличимо от отсутствия диалога."""

    async def test_returns_already_empty_status_not_no_active_conversation(self) -> None:
        users = FakeUserRepository()
        user = await _seed_user(users, telegram_user_id=8)
        conversations = SpyConversationRepository(FakeConversationRepository())
        active = await conversations.get_or_create_active(user.id)
        use_case, _, _, messages = _make_use_case(users=users, conversations=conversations)

        result = await use_case.execute(_make_command(telegram_user_id=8))

        assert result.status == ClearConversationStatus.ALREADY_EMPTY
        assert result.status != ClearConversationStatus.NO_ACTIVE_CONVERSATION
        assert result.conversation_id == active.id
        assert result.deleted_count == 0
        assert messages.clear_calls == [active.id]

    async def test_repeated_clear_on_empty_history_does_not_raise(self) -> None:
        users = FakeUserRepository()
        user = await _seed_user(users, telegram_user_id=8)
        conversations = SpyConversationRepository(FakeConversationRepository())
        await conversations.get_or_create_active(user.id)
        use_case, _, _, _ = _make_use_case(users=users, conversations=conversations)

        first_result = await use_case.execute(_make_command(telegram_user_id=8))
        second_result = await use_case.execute(_make_command(telegram_user_id=8))

        assert first_result.status == ClearConversationStatus.ALREADY_EMPTY
        assert second_result.status == ClearConversationStatus.ALREADY_EMPTY


class TestConversationIsNeitherDeletedNorClosedNorRecreated:
    """
    Обязательные сценарии: `Conversation` не удаляется, не закрывается и
    новый `Conversation` не создаётся — доказано и по состоянию, и по
    факту отсутствия вызова `.save()`/`.close()`.
    """

    async def test_conversation_is_not_deleted(self) -> None:
        users = FakeUserRepository()
        user = await _seed_user(users, telegram_user_id=9)
        conversations = SpyConversationRepository(FakeConversationRepository())
        active = await conversations.get_or_create_active(user.id)
        use_case, _, _, _ = _make_use_case(users=users, conversations=conversations)

        await use_case.execute(_make_command(telegram_user_id=9))

        assert await conversations.get_by_id(active.id) is not None

    async def test_conversation_is_not_closed(self) -> None:
        users = FakeUserRepository()
        user = await _seed_user(users, telegram_user_id=9)
        conversations = SpyConversationRepository(FakeConversationRepository())
        active = await conversations.get_or_create_active(user.id)
        use_case, _, _, _ = _make_use_case(users=users, conversations=conversations)

        await use_case.execute(_make_command(telegram_user_id=9))

        stored = await conversations.get_by_id(active.id)
        assert stored is not None
        assert stored.closed_at is None
        assert stored.is_active
        assert conversations.close_calls == 0

    async def test_no_new_conversation_is_created(self) -> None:
        users = FakeUserRepository()
        user = await _seed_user(users, telegram_user_id=9)
        conversations = SpyConversationRepository(FakeConversationRepository())
        await conversations.get_or_create_active(user.id)
        use_case, _, _, _ = _make_use_case(users=users, conversations=conversations)

        await use_case.execute(_make_command(telegram_user_id=9))

        assert conversations.save_calls == 0


class TestNoLLMDependency:
    """
    Обязательный сценарий: use case не принимает `LLMProvider` вовсе —
    архитектурный факт, а не только поведение в рантайме.
    """

    def test_constructor_does_not_accept_llm_provider(self) -> None:
        parameters = inspect.signature(ClearConversation.__init__).parameters

        assert "llm_provider" not in parameters
        assert set(parameters) - {"self"} == {"repositories"}
