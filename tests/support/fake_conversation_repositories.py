"""
In-memory fake-реализации `UserRepository`/`ConversationRepository`/
`MessageRepository` (`application/user/ports.py`,
`application/conversation/ports.py`) — общий тестовый helper для всех
unit-тестов, использующих `ProcessUserMessage` (Sprint 2, задача S2-06):
`tests/unit/application/test_process_user_message.py`,
`tests/unit/presentation/telegram/test_messages_handler.py`,
`tests/e2e/test_conversation_scenario.py`.

Никакого SQLAlchemy (backlog_2.md §9: «unit-тесты не должны использовать
SQLAlchemy») — только словари в памяти. Реальный persistence-поток
проверяет `tests/integration/test_process_user_message_persistence.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from dekoder.application.conversation.ports import ConversationRepositories, ConversationRepositoriesFactory
from dekoder.domain.conversation.entities import Conversation, Message
from dekoder.domain.user.entities import User


class FakeUserRepository:
    """In-memory fake порта `UserRepository`."""

    def __init__(self) -> None:
        self._by_telegram_user_id: dict[int, User] = {}

    async def get_by_id(self, user_id: UUID) -> User | None:
        for user in self._by_telegram_user_id.values():
            if user.id == user_id:
                return user
        return None

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> User | None:
        return self._by_telegram_user_id.get(telegram_user_id)

    async def save(self, user: User) -> User:
        self._by_telegram_user_id[user.telegram_user_id] = user
        return user

    async def get_or_create_by_telegram_user_id(self, telegram_user_id: int) -> User:
        existing = self._by_telegram_user_id.get(telegram_user_id)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        user = User(id=uuid4(), telegram_user_id=telegram_user_id, created_at=now, updated_at=now)
        self._by_telegram_user_id[telegram_user_id] = user
        return user


class FakeConversationRepository:
    """In-memory fake порта `ConversationRepository`."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, Conversation] = {}

    async def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        return self._by_id.get(conversation_id)

    async def get_active_by_user_id(self, user_id: UUID) -> Conversation | None:
        for conversation in self._by_id.values():
            if conversation.user_id == user_id and conversation.is_active:
                return conversation
        return None

    async def save(self, conversation: Conversation) -> Conversation:
        self._by_id[conversation.id] = conversation
        return conversation

    async def close(self, conversation: Conversation) -> Conversation:
        self._by_id[conversation.id] = conversation
        return conversation

    async def get_or_create_active(self, user_id: UUID) -> Conversation:
        existing = await self.get_active_by_user_id(user_id)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        conversation = Conversation(id=uuid4(), user_id=user_id, created_at=now, updated_at=now, closed_at=None)
        self._by_id[conversation.id] = conversation
        return conversation


class FakeMessageRepository:
    """In-memory fake порта `MessageRepository`."""

    def __init__(self) -> None:
        self._by_conversation: dict[UUID, list[Message]] = {}
        self.saved: list[Message] = []

    async def save(self, message: Message) -> Message:
        self._by_conversation.setdefault(message.conversation_id, []).append(message)
        self.saved.append(message)
        return message

    async def history(self, conversation_id: UUID) -> list[Message]:
        return list(self._by_conversation.get(conversation_id, []))

    async def clear(self, conversation_id: UUID) -> int:
        count = len(self._by_conversation.get(conversation_id, []))
        self._by_conversation[conversation_id] = []
        return count


def make_in_memory_repositories_factory(
    users: FakeUserRepository | None = None,
    conversations: FakeConversationRepository | None = None,
    messages: FakeMessageRepository | None = None,
) -> ConversationRepositoriesFactory:
    """
    Собирает `ConversationRepositoriesFactory` поверх in-memory fake-реализаций.
    Передавайте одни и те же fake-репозитории между несколькими вызовами
    use case, чтобы смоделировать «продолжение того же диалога».
    """
    users = users if users is not None else FakeUserRepository()
    conversations = conversations if conversations is not None else FakeConversationRepository()
    messages = messages if messages is not None else FakeMessageRepository()

    @asynccontextmanager
    async def _factory() -> AsyncIterator[ConversationRepositories]:
        yield ConversationRepositories(users=users, conversations=conversations, messages=messages)

    return _factory
