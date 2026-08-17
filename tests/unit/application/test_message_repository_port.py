"""
Тесты контракта MessageRepository (application/conversation/ports.py,
задача S2-05) на fake-реализации (in-memory dict) — без обращения к
SQLAlchemy/SQLite. Стиль — как у
`tests/unit/application/test_conversation_repository_port.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from dekoder.application.conversation.ports import MessageRepository
from dekoder.domain.conversation.entities import Message, MessageRole


class FakeMessageRepository:
    """Fake без наследования от MessageRepository — Protocol допускает структурную типизацию."""

    def __init__(self) -> None:
        self._messages_by_id: dict[UUID, Message] = {}

    async def save(self, message: Message) -> Message:
        self._messages_by_id[message.id] = message
        return message

    async def history(self, conversation_id: UUID) -> list[Message]:
        matching = [message for message in self._messages_by_id.values() if message.conversation_id == conversation_id]
        return sorted(matching, key=lambda message: (message.created_at, message.id))

    async def clear(self, conversation_id: UUID) -> int:
        to_delete = [
            message_id
            for message_id, message in self._messages_by_id.items()
            if message.conversation_id == conversation_id
        ]
        for message_id in to_delete:
            del self._messages_by_id[message_id]
        return len(to_delete)


def _make_message(
    conversation_id: UUID | None = None,
    *,
    role: MessageRole = MessageRole.USER,
    content: str = "hello",
    created_at: datetime | None = None,
    message_id: UUID | None = None,
) -> Message:
    return Message(
        id=message_id or uuid4(),
        conversation_id=conversation_id or uuid4(),
        role=role,
        content=content,
        created_at=created_at or datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )


class TestMessageRepositoryPortIsFakeable:
    def test_fake_satisfies_the_protocol_structurally(self) -> None:
        fake = FakeMessageRepository()

        assert isinstance(fake, MessageRepository)


class TestSave:
    async def test_save_returns_the_saved_entity_with_id_and_content_preserved(self) -> None:
        fake: MessageRepository = FakeMessageRepository()
        message = _make_message(content="Привет!")

        result = await fake.save(message)

        assert result == message
        assert result.id == message.id
        assert result.content == "Привет!"


class TestHistory:
    async def test_returns_empty_list_for_conversation_without_messages(self) -> None:
        fake: MessageRepository = FakeMessageRepository()

        result = await fake.history(uuid4())

        assert result == []

    async def test_returns_only_messages_of_the_requested_conversation(self) -> None:
        fake: MessageRepository = FakeMessageRepository()
        conversation_a = uuid4()
        conversation_b = uuid4()
        message_a = _make_message(conversation_a, content="a")
        message_b = _make_message(conversation_b, content="b")
        await fake.save(message_a)
        await fake.save(message_b)

        result_a = await fake.history(conversation_a)
        result_b = await fake.history(conversation_b)

        assert result_a == [message_a]
        assert result_b == [message_b]

    async def test_returns_messages_sorted_by_created_at_then_id_regardless_of_insertion_order(self) -> None:
        fake: MessageRepository = FakeMessageRepository()
        conversation_id = uuid4()
        base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        first = _make_message(conversation_id, content="first", created_at=base_time)
        second = _make_message(conversation_id, content="second", created_at=base_time + timedelta(minutes=1))
        third = _make_message(conversation_id, content="third", created_at=base_time + timedelta(minutes=2))
        # Сохраняем не по порядку.
        await fake.save(third)
        await fake.save(first)
        await fake.save(second)

        result = await fake.history(conversation_id)

        assert result == [first, second, third]


class TestClear:
    async def test_clear_removes_only_messages_of_the_target_conversation(self) -> None:
        fake: MessageRepository = FakeMessageRepository()
        conversation_a = uuid4()
        conversation_b = uuid4()
        await fake.save(_make_message(conversation_a, content="a1"))
        await fake.save(_make_message(conversation_a, content="a2"))
        message_b = await fake.save(_make_message(conversation_b, content="b1"))

        deleted_count = await fake.clear(conversation_a)

        assert deleted_count == 2
        assert await fake.history(conversation_a) == []
        assert await fake.history(conversation_b) == [message_b]

    async def test_clear_on_empty_history_is_idempotent_and_returns_zero(self) -> None:
        fake: MessageRepository = FakeMessageRepository()
        conversation_id = uuid4()

        first_call = await fake.clear(conversation_id)
        second_call = await fake.clear(conversation_id)

        assert first_call == 0
        assert second_call == 0
