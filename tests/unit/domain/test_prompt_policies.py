"""
Тесты `TokenBudgetPolicy` (domain/prompt/policies.py, задачи S4-02/S4-06,
ADR-4.4/4.5).

Оценка размера в этих тестах — простой счётчик символов
(`len(text)`, эквивалент реализации `application/prompt/services/
token_budget.py`, задача S4-06) — сам класс не привязан к конкретной
эвристике (принимает `estimate_size` через конструктор).
"""

from __future__ import annotations

from dekoder.application.conversation.dto import LLMMessage
from dekoder.domain.prompt.policies import TokenBudgetPolicy
from dekoder.domain.prompt.value_objects import (
    SECTION_BASE_INSTRUCTION,
    SECTION_KNOWLEDGE,
    SECTION_MEMORY,
    SECTION_PROFILE_PARAMETERS,
    SECTION_RESPONSE_FORMAT,
    SECTION_SAFETY_RULES,
    PromptSection,
)


def _policy() -> TokenBudgetPolicy:
    return TokenBudgetPolicy(estimate_size=len)


def _messages(*contents: str) -> list[LLMMessage]:
    return [LLMMessage(role="user", content=content) for content in contents]


class TestEnforceWithinBudget:
    def test_returns_input_unchanged_when_already_within_budget(self) -> None:
        sections = [PromptSection(name=SECTION_BASE_INSTRUCTION, text="короткий текст")]
        messages = _messages("привет")

        result_sections, result_messages = _policy().enforce(sections, messages, budget=1000)

        assert result_sections == sections
        assert result_messages == messages


class TestEnforceTrimsHistoryOldestFirst:
    def test_removes_oldest_message_first(self) -> None:
        sections = [PromptSection(name=SECTION_BASE_INSTRUCTION, text="")]
        messages = _messages("a" * 10, "b" * 10, "c" * 10)  # 30 символов суммарно

        result_sections, result_messages = _policy().enforce(sections, messages, budget=20)

        # Старейшее ("a"*10) удалено первым; текущий запрос ("c"*10) сохранён.
        assert result_messages == messages[1:]
        assert result_sections == sections

    def test_stops_as_soon_as_budget_is_satisfied(self) -> None:
        messages = _messages("a" * 5, "b" * 5, "c" * 5, "d" * 5)  # 20 символов

        _, result_messages = _policy().enforce([], messages, budget=16)

        # Удалить достаточно одно сообщение (20 -> 15 <= 16).
        assert result_messages == messages[1:]

    def test_never_removes_the_last_message(self) -> None:
        messages = _messages("a" * 100)

        _, result_messages = _policy().enforce([], messages, budget=1)

        assert result_messages == messages

    def test_deterministic_for_same_input(self) -> None:
        sections = [PromptSection(name=SECTION_BASE_INSTRUCTION, text="x" * 5)]
        messages = _messages("a" * 10, "b" * 10, "c" * 10)

        first = _policy().enforce(sections, messages, budget=20)
        second = _policy().enforce(sections, messages, budget=20)

        assert first == second


class TestEnforceProtectsUntouchableTiers:
    def test_section_1_2_3_and_8_are_never_trimmed_even_when_oversized(self) -> None:
        oversized_sections = [
            PromptSection(name=SECTION_BASE_INSTRUCTION, text="a" * 50),
            PromptSection(name=SECTION_SAFETY_RULES, text="b" * 50),
            PromptSection(name=SECTION_PROFILE_PARAMETERS, text="c" * 50),
            PromptSection(name=SECTION_RESPONSE_FORMAT, text="d" * 50),
        ]
        messages = _messages("текущий запрос")

        result_sections, result_messages = _policy().enforce(oversized_sections, messages, budget=10)

        # Бюджет (10) заведомо меньше суммарного размера неприкосновенных
        # секций (200+) — результат остаётся превышающим бюджет, но секции
        # и единственное сообщение (текущий запрос) не тронуты (ADR-4.5, AC-2).
        assert result_sections == oversized_sections
        assert result_messages == messages

    def test_last_message_untouchable_even_with_huge_history(self) -> None:
        messages = _messages(*(f"старое {i}" for i in range(20)), "текущий запрос")

        _, result_messages = _policy().enforce([], messages, budget=1)

        assert result_messages == [messages[-1]]
        assert result_messages[0].content == "текущий запрос"


class TestEnforceMemoryAndKnowledgeTiers:
    def test_memory_section_is_cleared_before_history_is_trimmed(self) -> None:
        sections = [
            PromptSection(name=SECTION_BASE_INSTRUCTION, text="база"),
            PromptSection(name=SECTION_MEMORY, text="m" * 50),
        ]
        messages = _messages("текущий запрос")

        result_sections, result_messages = _policy().enforce(sections, messages, budget=10)

        memory_section = next(section for section in result_sections if section.name == SECTION_MEMORY)
        assert memory_section.text == ""
        assert result_messages == messages

    def test_knowledge_section_is_cleared_when_memory_alone_is_not_enough(self) -> None:
        sections = [
            PromptSection(name=SECTION_MEMORY, text="m" * 50),
            PromptSection(name=SECTION_KNOWLEDGE, text="k" * 50),
        ]
        messages = _messages("текущий запрос")

        result_sections, _ = _policy().enforce(sections, messages, budget=10)

        assert all(section.text == "" for section in result_sections)

    def test_memory_and_knowledge_tiers_are_real_noop_branches_on_empty_input(self) -> None:
        sections = [
            PromptSection(name=SECTION_BASE_INSTRUCTION, text="база"),
            PromptSection(name=SECTION_MEMORY, text=""),
            PromptSection(name=SECTION_KNOWLEDGE, text=""),
        ]
        messages = _messages("текущий запрос")

        result_sections, result_messages = _policy().enforce(sections, messages, budget=1000)

        assert result_sections == sections
        assert result_messages == messages

    def test_untouched_sections_are_not_affected_by_memory_reduction(self) -> None:
        sections = [
            PromptSection(name=SECTION_BASE_INSTRUCTION, text="база"),
            PromptSection(name=SECTION_MEMORY, text="m" * 50),
        ]
        messages = _messages("текущий запрос")

        result_sections, _ = _policy().enforce(sections, messages, budget=10)

        base_section = next(section for section in result_sections if section.name == SECTION_BASE_INSTRUCTION)
        assert base_section.text == "база"
