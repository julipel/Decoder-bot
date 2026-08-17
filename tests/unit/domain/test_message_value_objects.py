"""Тесты доменных value objects первого вертикального среза (domain/conversation/value_objects.py)."""

from __future__ import annotations

import dataclasses

import pytest

from dekoder.domain.conversation.value_objects import MessageText, ModelId, ProviderId


class TestMessageText:
    def test_creates_with_valid_text(self) -> None:
        message = MessageText("Привет, как дела?")

        assert message.value == "Привет, как дела?"

    def test_strips_leading_and_trailing_whitespace(self) -> None:
        message = MessageText("   Привет   ")

        assert message.value == "Привет"

    def test_empty_text_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="не может быть пустым"):
            MessageText("")

    def test_whitespace_only_text_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="не может быть пустым"):
            MessageText("   \t\n  ")

    def test_text_within_max_length_is_accepted(self) -> None:
        text = "a" * MessageText.MAX_LENGTH

        message = MessageText(text)

        assert len(message.value) == MessageText.MAX_LENGTH

    def test_text_exceeding_max_length_raises_value_error(self) -> None:
        text = "a" * (MessageText.MAX_LENGTH + 1)

        with pytest.raises(ValueError, match="превышает максимальную длину"):
            MessageText(text)

    def test_is_immutable(self) -> None:
        message = MessageText("исходный текст")

        with pytest.raises(dataclasses.FrozenInstanceError):
            message.value = "новый текст"  # type: ignore[misc]

    def test_has_no_dict_due_to_slots(self) -> None:
        # frozen=True + slots=True: присвоение имени вне __slots__ падает
        # в реализации dataclasses с TypeError, а не AttributeError/
        # FrozenInstanceError (CPython 3.12) — важен сам факт отказа,
        # инстанс всё равно не получает произвольных атрибутов.
        message = MessageText("текст")

        with pytest.raises((AttributeError, TypeError)):
            message.extra = "нельзя"  # type: ignore[attr-defined]

    def test_equality_is_value_based(self) -> None:
        assert MessageText("привет") == MessageText("привет")
        assert MessageText("привет") != MessageText("пока")


class TestModelId:
    def test_creates_with_valid_value(self) -> None:
        model_id = ModelId("openai/gpt-4o-mini")

        assert model_id.value == "openai/gpt-4o-mini"

    def test_strips_leading_and_trailing_whitespace(self) -> None:
        model_id = ModelId("  openai/gpt-4o-mini  ")

        assert model_id.value == "openai/gpt-4o-mini"

    def test_empty_value_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="не может быть пустым"):
            ModelId("")

    def test_whitespace_only_value_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="не может быть пустым"):
            ModelId("   ")

    def test_is_immutable(self) -> None:
        model_id = ModelId("openai/gpt-4o-mini")

        with pytest.raises(dataclasses.FrozenInstanceError):
            model_id.value = "another/model"  # type: ignore[misc]


class TestProviderId:
    def test_creates_with_valid_value(self) -> None:
        provider_id = ProviderId("test-provider")

        assert provider_id.value == "test-provider"

    def test_strips_leading_and_trailing_whitespace(self) -> None:
        provider_id = ProviderId("  test-provider  ")

        assert provider_id.value == "test-provider"

    def test_empty_value_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="не может быть пустым"):
            ProviderId("")

    def test_whitespace_only_value_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="не может быть пустым"):
            ProviderId("   ")

    def test_is_immutable(self) -> None:
        provider_id = ProviderId("test-provider")

        with pytest.raises(dataclasses.FrozenInstanceError):
            provider_id.value = "another-provider"  # type: ignore[misc]
