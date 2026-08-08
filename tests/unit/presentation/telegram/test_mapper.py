"""Тесты presentation/telegram/mapper.py — без обращения к реальному Telegram API."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from telegram import Update

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.presentation.telegram.mapper import (
    TELEGRAM_SAFE_MESSAGE_LIMIT,
    split_message,
    to_clear_conversation_command,
    to_command,
    to_create_memory_record_command,
    to_delete_memory_record_command,
    to_get_active_profile_command,
    to_get_selected_model_command,
    to_list_available_models_command,
    to_list_memory_records_command,
    to_select_model_command,
    to_select_profile_command,
    to_start_new_conversation_command,
)


def _make_update(text: str = "Привет!", user_id: int = 12345) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.text = text
    return update


def _make_callback_update(user_id: int = 12345) -> MagicMock:
    """Update с callback_query (нажатие inline-кнопки), без effective_user — тот же паттерн, что и в
    test_model_handler.py/test_profile_handler.py."""
    update = MagicMock(spec=Update)
    update.effective_user = None
    query = MagicMock()
    query.from_user = MagicMock(id=user_id)
    update.callback_query = query
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


class TestToClearConversationCommand:
    def test_maps_telegram_user_id(self) -> None:
        command = to_clear_conversation_command(_make_update(user_id=999))

        assert command.telegram_user_id == 999

    def test_generates_a_correlation_id(self) -> None:
        command = to_clear_conversation_command(_make_update())

        assert command.correlation_id

    def test_generates_a_fresh_correlation_id_each_call(self) -> None:
        first = to_clear_conversation_command(_make_update())
        second = to_clear_conversation_command(_make_update())

        assert first.correlation_id != second.correlation_id

    def test_raises_when_user_is_missing(self) -> None:
        update = _make_update()
        update.effective_user = None

        with pytest.raises(ValueError):
            to_clear_conversation_command(update)


class TestToStartNewConversationCommand:
    def test_maps_telegram_user_id(self) -> None:
        command = to_start_new_conversation_command(_make_update(user_id=999))

        assert command.telegram_user_id == 999

    def test_generates_a_correlation_id(self) -> None:
        command = to_start_new_conversation_command(_make_update())

        assert command.correlation_id

    def test_generates_a_fresh_correlation_id_each_call(self) -> None:
        first = to_start_new_conversation_command(_make_update())
        second = to_start_new_conversation_command(_make_update())

        assert first.correlation_id != second.correlation_id

    def test_raises_when_user_is_missing(self) -> None:
        update = _make_update()
        update.effective_user = None

        with pytest.raises(ValueError):
            to_start_new_conversation_command(update)


class TestToGetActiveProfileCommand:
    def test_maps_telegram_user_id(self) -> None:
        command = to_get_active_profile_command(_make_update(user_id=999))

        assert command.telegram_user_id == 999

    def test_generates_a_correlation_id(self) -> None:
        command = to_get_active_profile_command(_make_update())

        assert command.correlation_id

    def test_generates_a_fresh_correlation_id_each_call(self) -> None:
        first = to_get_active_profile_command(_make_update())
        second = to_get_active_profile_command(_make_update())

        assert first.correlation_id != second.correlation_id

    def test_raises_when_user_is_missing(self) -> None:
        update = _make_update()
        update.effective_user = None

        with pytest.raises(ValueError):
            to_get_active_profile_command(update)


class TestToSelectProfileCommand:
    def test_maps_telegram_user_id_from_callback_query(self) -> None:
        profile_id = uuid4()

        command = to_select_profile_command(_make_callback_update(user_id=999), profile_id)

        assert command.telegram_user_id == 999
        assert command.profile_id == profile_id

    def test_generates_a_correlation_id(self) -> None:
        command = to_select_profile_command(_make_callback_update(), uuid4())

        assert command.correlation_id

    def test_generates_a_fresh_correlation_id_each_call(self) -> None:
        first = to_select_profile_command(_make_callback_update(), uuid4())
        second = to_select_profile_command(_make_callback_update(), uuid4())

        assert first.correlation_id != second.correlation_id

    def test_raises_when_callback_query_is_missing(self) -> None:
        update = _make_callback_update()
        update.callback_query = None

        with pytest.raises(ValueError):
            to_select_profile_command(update, uuid4())


class TestToCreateMemoryRecordCommand:
    def test_maps_telegram_user_id_and_text(self) -> None:
        command = to_create_memory_record_command(_make_update(user_id=999), "текст факта")

        assert command.telegram_user_id == 999
        assert command.text == "текст факта"

    def test_generates_a_correlation_id(self) -> None:
        command = to_create_memory_record_command(_make_update(), "текст")

        assert command.correlation_id

    def test_generates_a_fresh_correlation_id_each_call(self) -> None:
        first = to_create_memory_record_command(_make_update(), "текст")
        second = to_create_memory_record_command(_make_update(), "текст")

        assert first.correlation_id != second.correlation_id

    def test_raises_when_user_is_missing(self) -> None:
        update = _make_update()
        update.effective_user = None

        with pytest.raises(ValueError):
            to_create_memory_record_command(update, "текст")


class TestToListMemoryRecordsCommand:
    def test_maps_telegram_user_id(self) -> None:
        command = to_list_memory_records_command(_make_update(user_id=999))

        assert command.telegram_user_id == 999

    def test_generates_a_correlation_id(self) -> None:
        command = to_list_memory_records_command(_make_update())

        assert command.correlation_id

    def test_generates_a_fresh_correlation_id_each_call(self) -> None:
        first = to_list_memory_records_command(_make_update())
        second = to_list_memory_records_command(_make_update())

        assert first.correlation_id != second.correlation_id

    def test_raises_when_user_is_missing(self) -> None:
        update = _make_update()
        update.effective_user = None

        with pytest.raises(ValueError):
            to_list_memory_records_command(update)


class TestToDeleteMemoryRecordCommand:
    def test_maps_telegram_user_id_from_callback_query(self) -> None:
        record_id = uuid4()

        command = to_delete_memory_record_command(_make_callback_update(user_id=999), record_id)

        assert command.telegram_user_id == 999
        assert command.record_id == record_id

    def test_generates_a_correlation_id(self) -> None:
        command = to_delete_memory_record_command(_make_callback_update(), uuid4())

        assert command.correlation_id

    def test_generates_a_fresh_correlation_id_each_call(self) -> None:
        first = to_delete_memory_record_command(_make_callback_update(), uuid4())
        second = to_delete_memory_record_command(_make_callback_update(), uuid4())

        assert first.correlation_id != second.correlation_id

    def test_raises_when_callback_query_is_missing(self) -> None:
        update = _make_callback_update()
        update.callback_query = None

        with pytest.raises(ValueError):
            to_delete_memory_record_command(update, uuid4())


class TestToListAvailableModelsCommand:
    def test_maps_telegram_user_id(self) -> None:
        command = to_list_available_models_command(_make_update(user_id=999))

        assert command.telegram_user_id == 999

    def test_generates_a_correlation_id(self) -> None:
        command = to_list_available_models_command(_make_update())

        assert command.correlation_id

    def test_generates_a_fresh_correlation_id_each_call(self) -> None:
        first = to_list_available_models_command(_make_update())
        second = to_list_available_models_command(_make_update())

        assert first.correlation_id != second.correlation_id

    def test_raises_when_user_is_missing(self) -> None:
        update = _make_update()
        update.effective_user = None

        with pytest.raises(ValueError):
            to_list_available_models_command(update)


class TestToGetSelectedModelCommand:
    def test_maps_telegram_user_id(self) -> None:
        command = to_get_selected_model_command(_make_update(user_id=999))

        assert command.telegram_user_id == 999

    def test_generates_a_correlation_id(self) -> None:
        command = to_get_selected_model_command(_make_update())

        assert command.correlation_id

    def test_generates_a_fresh_correlation_id_each_call(self) -> None:
        first = to_get_selected_model_command(_make_update())
        second = to_get_selected_model_command(_make_update())

        assert first.correlation_id != second.correlation_id

    def test_raises_when_user_is_missing(self) -> None:
        update = _make_update()
        update.effective_user = None

        with pytest.raises(ValueError):
            to_get_selected_model_command(update)


class TestToSelectModelCommand:
    def test_maps_telegram_user_id_from_callback_query(self) -> None:
        model_id = ModelId("anthropic/claude-3.5-sonnet")

        command = to_select_model_command(_make_callback_update(user_id=999), model_id)

        assert command.telegram_user_id == 999
        assert command.model_id == model_id

    def test_generates_a_correlation_id(self) -> None:
        command = to_select_model_command(_make_callback_update(), ModelId("anthropic/claude-3.5-sonnet"))

        assert command.correlation_id

    def test_generates_a_fresh_correlation_id_each_call(self) -> None:
        model_id = ModelId("anthropic/claude-3.5-sonnet")
        first = to_select_model_command(_make_callback_update(), model_id)
        second = to_select_model_command(_make_callback_update(), model_id)

        assert first.correlation_id != second.correlation_id

    def test_raises_when_callback_query_is_missing(self) -> None:
        update = _make_callback_update()
        update.callback_query = None

        with pytest.raises(ValueError):
            to_select_model_command(update, ModelId("anthropic/claude-3.5-sonnet"))


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
