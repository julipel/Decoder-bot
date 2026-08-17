"""
Тесты эвристики оценки размера (application/prompt/services/
token_budget.py::estimate_size, задача S4-06, ADR-4.4) и её интеграции
с `TokenBudgetPolicy` (`domain/prompt/policies.py`, ADR-4.5) через
`DeterministicPromptBuilder` (S4-05) — подтверждает, что обрезание
истории реально срабатывает end-to-end при использовании настоящей,
не искусственной (`len`) эвристики.

Полная матрица тиров ADR-4.5 (неприкосновенность секций 1/2/3/последнего
сообщения, порядок обрезания истории, no-op тиры 4/5) уже покрыта
`tests/unit/domain/test_prompt_policies.py` (задача S4-02) — этот файл
не дублирует её, а проверяет то, что специфично для S4-06: саму
эвристику и её реальное использование в сборке.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from dekoder.application.prompt.services.prompt_builder import DeterministicPromptBuilder
from dekoder.application.prompt.services.token_budget import estimate_size
from dekoder.domain.conversation.entities import Message, MessageRole
from dekoder.domain.profile.entities import UserProfile
from dekoder.domain.profile.value_objects import ProfileStatus
from dekoder.domain.prompt.policies import TokenBudgetPolicy
from dekoder.domain.prompt.value_objects import PromptContext
from dekoder.infrastructure.prompts.file_template_repository import FileTemplateRepository


class TestEstimateSize:
    def test_counts_characters(self) -> None:
        assert estimate_size("привет") == 6

    def test_empty_text_has_zero_size(self) -> None:
        assert estimate_size("") == 0

    def test_is_deterministic(self) -> None:
        text = "одна и та же строка"
        assert estimate_size(text) == estimate_size(text)


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _make_profile() -> UserProfile:
    created_at = _now()
    return UserProfile(
        id=uuid4(),
        name="Деловой",
        description="Кратко и по делу.",
        system_instruction="Отвечай кратко и по делу.",
        response_style="деловой, лаконичный",
        target_audience="широкая аудитория",
        formality_level="формальный",
        preferred_structure="вывод в начале",
        forbidden_phrasing=(),
        preferred_model=None,
        response_length_hint=None,
        additional_constraints="",
        status=ProfileStatus.ACTIVE,
        is_system=True,
        is_default=True,
        created_at=created_at,
        updated_at=created_at,
    )


def _make_message(role: MessageRole, content: str) -> Message:
    return Message(id=uuid4(), conversation_id=uuid4(), role=role, content=content, created_at=_now())


class TestEndToEndBudgetEnforcementWithRealEstimator:
    """
    Sprint 4, задача S4-06 (тестирование): «искусственно большая история
    обрезается с самого старого элемента» — здесь через полный
    `DeterministicPromptBuilder.build()` с реальными сид-шаблонами и
    реальной эвристикой `estimate_size`, не через `TokenBudgetPolicy`
    напрямую (уже покрыто в S4-02) — доказывает, что обрезание реально
    срабатывает по всему стеку Prompt Engine, а не только внутри
    изолированного юнита политики.
    """

    def _builder(self, budget: int) -> DeterministicPromptBuilder:
        return DeterministicPromptBuilder(
            template_repository=FileTemplateRepository(),
            token_budget_policy=TokenBudgetPolicy(estimate_size=estimate_size),
            budget=budget,
        )

    def test_long_dialogue_history_is_trimmed_when_budget_is_small(self) -> None:
        long_history = [_make_message(MessageRole.USER, f"Сообщение номер {i} " * 20) for i in range(30)]
        current_request = _make_message(MessageRole.USER, "Текущий запрос")
        context = PromptContext(profile=_make_profile(), dialogue_history=[*long_history, current_request])

        result = self._builder(budget=500).build(context)

        assert len(result.messages) < len(long_history) + 1
        # Текущий запрос — последний элемент — сохранён всегда (ADR-4.5).
        assert result.messages[-1].content == "Текущий запрос"
        # system_prompt (секции 1/2/3/8) не пострадал — он не входит в messages.
        assert result.system_prompt

    def test_short_dialogue_history_is_not_trimmed_with_generous_budget(self) -> None:
        history = [_make_message(MessageRole.USER, "Привет"), _make_message(MessageRole.ASSISTANT, "Здравствуйте!")]
        context = PromptContext(profile=_make_profile(), dialogue_history=history)

        result = self._builder(budget=1_000_000).build(context)

        assert len(result.messages) == len(history)

    def test_response_ok_even_when_history_trimmed_to_single_message(self) -> None:
        """Обрезание истории не ломает сборку — `build()` всегда возвращает валидный непустой `system_prompt`."""
        long_history = [_make_message(MessageRole.USER, "x" * 200) for _ in range(50)]
        current_request = _make_message(MessageRole.USER, "запрос")
        context = PromptContext(profile=_make_profile(), dialogue_history=[*long_history, current_request])

        result = self._builder(budget=1).build(context)

        assert len(result.messages) == 1
        assert result.messages[0].content == "запрос"
        assert result.system_prompt
