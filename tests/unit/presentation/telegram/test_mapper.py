"""Тесты presentation/telegram/mapper.py — без обращения к реальному Telegram API."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from telegram import Update

from dekoder.presentation.telegram.mapper import (
    TELEGRAM_SAFE_MESSAGE_LIMIT,
    split_message,
    to_command,
)


def _make_update(text: str = "Привет!", user_id: int = 12345) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.text = text
    return update


class TestToCommand:
    def test_maps_text_and_telegram_user_id(self) -> None:
        command = to_command(_make_update(text="Привет!", user_id=999))

        assert command.message_text == "Привет!"
        assert command.telegram_user_id == 999
        assert command.model_id is None

    def test_generates_a_correlation_id(self) -> None:
        command = to_command(_make_update())

        assert command.correlation_id

    def test_generates_a_fresh_correlation_id_each_call(self) -> None:
        first = to_command(_make_update())
        second = to_command(_make_update())

        assert first.correlation_id != second.correlation_id

    def test_raises_when_message_has_no_text(self) -> None:
        update = _make_update()
        update.effective_message.text = None

        with pytest.raises(ValueError):
            to_command(update)

    def test_raises_when_user_is_missing(self) -> None:
        update = _make_update()
        update.effective_user = None

        with pytest.raises(ValueError):
            to_command(update)

    def test_raises_when_message_is_missing(self) -> None:
        update = _make_update()
        update.effective_message = None

        with pytest.raises(ValueError):
            to_command(update)


class TestSplitMessage:
    def test_returns_single_chunk_when_within_limit(self) -> None:
        assert split_message("short text") == ["short text"]

    def test_splits_text_exceeding_limit_into_bounded_chunks(self) -> None:
        text = "word " * 2000

        chunks = split_message(text)

        assert len(chunks) > 1
        assert all(0 < len(chunk) <= TELEGRAM_SAFE_MESSAGE_LIMIT for chunk in chunks)

    def test_preserves_all_words_across_chunks(self) -> None:
        text = "word " * 2000

        chunks = split_message(text)

        assert " ".join(chunks).split() == text.split()

    def test_respects_custom_limit(self) -> None:
        text = "one two three four five six seven eight nine ten"

        chunks = split_message(text, limit=15)

        assert all(len(chunk) <= 15 for chunk in chunks)
        assert " ".join(chunks).split() == text.split()

    def test_hard_cuts_when_no_whitespace_boundary_exists(self) -> None:
        text = "a" * 50

        chunks = split_message(text, limit=20)

        assert chunks == ["a" * 20, "a" * 20, "a" * 10]
