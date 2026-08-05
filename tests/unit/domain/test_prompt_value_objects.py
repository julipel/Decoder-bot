"""Тесты value objects Prompt Engine (domain/prompt/value_objects.py, задача S4-02)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from dekoder.application.conversation.dto import LLMMessage
from dekoder.domain.conversation.entities import Message, MessageRole
from dekoder.domain.profile.entities import UserProfile
from dekoder.domain.profile.value_objects import ProfileStatus
from dekoder.domain.prompt.value_objects import PromptBuildResult, PromptContext, PromptSection


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _make_profile(**overrides: object) -> UserProfile:
    created_at = _now()
    defaults: dict[str, object] = {
        "id": uuid4(),
        "name": "Деловой",
        "description": "Кратко и по делу.",
        "system_instruction": "Отвечай кратко и по делу.",
        "response_style": "формальный",
        "target_audience": "широкая аудитория",
        "formality_level": "формальный",
        "preferred_structure": "выводы в начале",
        "forbidden_phrasing": (),
        "preferred_model": None,
        "response_length_hint": None,
        "additional_constraints": "",
        "status": ProfileStatus.ACTIVE,
        "is_system": True,
        "is_default": True,
        "created_at": created_at,
        "updated_at": created_at,
    }
    defaults.update(overrides)
    return UserProfile(**defaults)  # type: ignore[arg-type]


def _make_message(role: MessageRole = MessageRole.USER, content: str = "Привет!") -> Message:
    return Message(id=uuid4(), conversation_id=uuid4(), role=role, content=content, created_at=_now())


class TestPromptSection:
    def test_allows_empty_text(self) -> None:
        section = PromptSection(name="memory_placeholder", text="")

        assert section.text == ""

    def test_is_frozen(self) -> None:
        section = PromptSection(name="base_instruction", text="текст")

        with pytest.raises(dataclasses.FrozenInstanceError):
            section.text = "другое"  # type: ignore[misc]


class TestPromptContext:
    def test_creates_with_default_empty_placeholders(self) -> None:
        history = [_make_message()]

        context = PromptContext(profile=_make_profile(), dialogue_history=history)

        assert context.confirmed_memory_facts == ()
        assert context.knowledge_fragments == ()
        assert context.dialogue_history == history

    def test_last_history_element_is_current_request_by_convention(self) -> None:
        first = _make_message(role=MessageRole.ASSISTANT, content="Чем помочь?")
        current = _make_message(role=MessageRole.USER, content="Текущий запрос")

        context = PromptContext(profile=_make_profile(), dialogue_history=[first, current])

        assert context.dialogue_history[-1] is current

    def test_empty_dialogue_history_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="dialogue_history"):
            PromptContext(profile=_make_profile(), dialogue_history=[])

    def test_accepts_non_empty_memory_and_knowledge_placeholders(self) -> None:
        context = PromptContext(
            profile=_make_profile(),
            dialogue_history=[_make_message()],
            confirmed_memory_facts=("пользователь любит краткие ответы",),
            knowledge_fragments=("фрагмент базы знаний",),
        )

        assert context.confirmed_memory_facts == ("пользователь любит краткие ответы",)
        assert context.knowledge_fragments == ("фрагмент базы знаний",)


class TestPromptBuildResult:
    def test_holds_system_prompt_messages_and_versions(self) -> None:
        sections = [PromptSection(name="base_instruction", text="Ты — ассистент.")]
        messages = [LLMMessage(role="user", content="Привет!")]

        result = PromptBuildResult(
            system_prompt="Ты — ассистент.",
            messages=messages,
            template_versions={"base_instruction": "1.0.0"},
            sections=sections,
        )

        assert result.system_prompt == "Ты — ассистент."
        assert result.messages == messages
        assert result.template_versions == {"base_instruction": "1.0.0"}
        assert result.sections == sections

    def test_is_frozen(self) -> None:
        result = PromptBuildResult(system_prompt="", messages=[], template_versions={}, sections=[])

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.system_prompt = "другое"  # type: ignore[misc]
