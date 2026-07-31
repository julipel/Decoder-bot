"""Тесты доменной сущности `Message` и `MessageRole` (domain/conversation/entities.py, задача S2-02)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from dekoder.domain.conversation.entities import Message, MessageRole


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


class TestMessageRole:
    def test_has_only_user_and_assistant(self) -> None:
        assert {role.value for role in MessageRole} == {"user", "assistant"}


class TestMessageCreation:
    def test_creates_user_message(self) -> None:
        message = Message(
            id=uuid4(),
            conversation_id=uuid4(),
            role=MessageRole.USER,
            content="Привет!",
            created_at=_now(),
        )

        assert message.role is MessageRole.USER
        assert message.content == "Привет!"

    def test_creates_assistant_message(self) -> None:
        message = Message(
            id=uuid4(),
            conversation_id=uuid4(),
            role=MessageRole.ASSISTANT,
            content="Здравствуйте!",
            created_at=_now(),
        )

        assert message.role is MessageRole.ASSISTANT


class TestMessageInvariants:
    def test_empty_content_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="пустым"):
            Message(id=uuid4(), conversation_id=uuid4(), role=MessageRole.USER, content="", created_at=_now())

    def test_whitespace_only_content_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="пустым"):
            Message(id=uuid4(), conversation_id=uuid4(), role=MessageRole.USER, content="   \t\n  ", created_at=_now())


class TestMessageImmutability:
    def test_is_frozen(self) -> None:
        message = Message(
            id=uuid4(), conversation_id=uuid4(), role=MessageRole.USER, content="текст", created_at=_now()
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            message.content = "другой текст"  # type: ignore[misc]
