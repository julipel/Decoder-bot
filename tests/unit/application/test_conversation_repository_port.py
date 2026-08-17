"""
Тесты контракта ConversationRepository (application/conversation/ports.py,
задача S2-04) на fake-реализации (in-memory dict) — без обращения к
SQLAlchemy/SQLite. Стиль — как у
`tests/unit/application/test_user_repository_port.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from dekoder.application.conversation.ports import ConversationRepository
from dekoder.domain.conversation.entities import Conversation


class FakeConversationRepository:
    """Fake без наследования от ConversationRepository — Protocol допускает структурную типизацию."""

    def __init__(self) -> None:
        self._conversations_by_id: dict[UUID, Conversation] = {}

    async def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        return self._conversations_by_id.get(conversation_id)

    async def get_active_by_user_id(self, user_id: UUID) -> Conversation | None:
        for conversation in self._conversations_by_id.values():
            if conversation.user_id == user_id and conversation.is_active:
                return conversation
        return None

    async def save(self, conversation: Conversation) -> Conversation:
        self._conversations_by_id[conversation.id] = conversation
        return conversation

    async def close(self, conversation: Conversation) -> Conversation:
        self._conversations_by_id[conversation.id] = conversation
        return conversation

    async def get_or_create_active(self, user_id: UUID) -> Conversation:
        existing = await self.get_active_by_user_id(user_id)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        new_conversation = Conversation(id=uuid4(), user_id=user_id, created_at=now, updated_at=now, closed_at=None)
        return await self.save(new_conversation)


def _make_conversation(user_id: UUID | None = None, *, closed_at: datetime | None = None) -> Conversation:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    return Conversation(
        id=uuid4(),
        user_id=user_id or uuid4(),
        created_at=now,
        updated_at=closed_at or now,
        closed_at=closed_at,
    )


class TestConversationRepositoryPortIsFakeable:
    def test_fake_satisfies_the_protocol_structurally(self) -> None:
        fake = FakeConversationRepository()

        assert isinstance(fake, ConversationRepository)


class TestGetById:
    async def test_returns_none_when_not_found(self) -> None:
        fake: ConversationRepository = FakeConversationRepository()

        result = await fake.get_by_id(uuid4())

        assert result is None

    async def test_returns_saved_conversation(self) -> None:
        fake: ConversationRepository = FakeConversationRepository()
        conversation = _make_conversation()
        await fake.save(conversation)

        result = await fake.get_by_id(conversation.id)

        assert result == conversation


class TestGetActiveByUserId:
    async def test_returns_none_when_no_conversation_exists(self) -> None:
        fake: ConversationRepository = FakeConversationRepository()

        result = await fake.get_active_by_user_id(uuid4())

        assert result is None

    async def test_returns_none_when_only_closed_conversation_exists(self) -> None:
        fake: ConversationRepository = FakeConversationRepository()
        user_id = uuid4()
        closed_at = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
        closed_conversation = _make_conversation(user_id, closed_at=closed_at)
        await fake.save(closed_conversation)

        result = await fake.get_active_by_user_id(user_id)

        assert result is None

    async def test_returns_active_conversation_ignoring_closed_ones(self) -> None:
        fake: ConversationRepository = FakeConversationRepository()
        user_id = uuid4()
        closed_at = datetime(2026, 1, 2, 12, 0, 0, tzinfo=UTC)
        closed_conversation = _make_conversation(user_id, closed_at=closed_at)
        active_conversation = _make_conversation(user_id)
        await fake.save(closed_conversation)
        await fake.save(active_conversation)

        result = await fake.get_active_by_user_id(user_id)

        assert result == active_conversation


class TestGetOrCreateActive:
    async def test_first_call_creates_active_conversation(self) -> None:
        fake: ConversationRepository = FakeConversationRepository()
        user_id = uuid4()

        created = await fake.get_or_create_active(user_id)

        assert created.user_id == user_id
        assert created.closed_at is None
        assert created.is_active
        assert await fake.get_by_id(created.id) == created

    async def test_repeated_call_returns_the_same_conversation_without_creating_a_new_one(self) -> None:
        fake = FakeConversationRepository()
        user_id = uuid4()

        first = await fake.get_or_create_active(user_id)
        second = await fake.get_or_create_active(user_id)

        assert first.id == second.id
        assert first == second
        assert len(fake._conversations_by_id) == 1

    async def test_after_close_creates_a_new_conversation_with_a_different_id_keeping_the_old_one(self) -> None:
        fake = FakeConversationRepository()
        user_id = uuid4()

        original = await fake.get_or_create_active(user_id)
        closed_at = original.created_at + timedelta(hours=1)
        original.close(closed_at)
        await fake.close(original)

        new_conversation = await fake.get_or_create_active(user_id)

        assert new_conversation.id != original.id
        assert new_conversation.is_active
        # Старый диалог остаётся в хранилище, доступен по id, закрыт.
        stored_original = await fake.get_by_id(original.id)
        assert stored_original is not None
        assert stored_original.closed_at == closed_at
        assert len(fake._conversations_by_id) == 2
