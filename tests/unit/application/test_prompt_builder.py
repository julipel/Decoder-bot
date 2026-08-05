"""
Тесты `DeterministicPromptBuilder` (application/prompt/services/
prompt_builder.py, задача S4-05, ADR-4.1/4.2/4.3/4.7/4.9).

`FakePromptTemplateRepository` — минимальный in-memory fake порта
`PromptTemplateRepository` (по стилю `tests/support/
fake_conversation_repositories.py`), не полагается на реальные
сид-шаблоны `infrastructure/prompts/templates/` — те проверяет отдельный
класс тестов ниже (`TestWithRealSeedTemplates`, ADR-4.7 DoD: «для
каждого из 4 сид-профилей»).

`TokenBudgetPolicy` внедряется настоящей (`domain/prompt/policies.py`) с
заведомо огромным бюджетом — эти тесты проверяют сборку, не сокращение
объёма (это S4-06); тем не менее вызов `enforce()` — часть реального
пути `build()`, не замокан.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from dekoder.application.prompt.services.prompt_builder import DeterministicPromptBuilder
from dekoder.domain.conversation.entities import Message, MessageRole
from dekoder.domain.profile.entities import UserProfile
from dekoder.domain.profile.value_objects import ProfileStatus
from dekoder.domain.prompt.entities import PromptTemplate, PromptTemplateStatus
from dekoder.domain.prompt.policies import TokenBudgetPolicy
from dekoder.domain.prompt.value_objects import (
    SECTION_BASE_INSTRUCTION,
    SECTION_KNOWLEDGE,
    SECTION_MEMORY,
    SECTION_PROFILE_PARAMETERS,
    SECTION_RESPONSE_FORMAT,
    SECTION_SAFETY_RULES,
    PromptContext,
)
from dekoder.infrastructure.prompts.file_template_repository import FileTemplateRepository
from dekoder.shared.errors import ApplicationError, InfrastructureError

_HUGE_BUDGET = 10_000_000


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _template(
    template_id: str,
    text: str,
    required_variables: tuple[str, ...] = (),
    *,
    version: str = "1.0.0",
) -> PromptTemplate:
    return PromptTemplate(
        id=template_id,
        name=template_id,
        version=version,
        purpose=template_id,
        text=text,
        required_variables=required_variables,
        status=PromptTemplateStatus.ACTIVE,
        updated_at=_now(),
    )


class FakePromptTemplateRepository:
    """In-memory fake порта `PromptTemplateRepository` — не читает файлы."""

    def __init__(self, templates: dict[str, PromptTemplate]) -> None:
        self._templates = templates

    def get(self, name: str) -> PromptTemplate:
        try:
            return self._templates[name]
        except KeyError as error:
            raise InfrastructureError(
                message=f"FakePromptTemplateRepository: шаблон '{name}' не найден",
                user_message="Ошибка конфигурации.",
                cause=error,
            ) from error

    def list_all(self) -> Sequence[PromptTemplate]:
        return list(self._templates.values())


def _default_templates() -> dict[str, PromptTemplate]:
    return {
        SECTION_BASE_INSTRUCTION: _template(SECTION_BASE_INSTRUCTION, "Базовая инструкция."),
        SECTION_SAFETY_RULES: _template(SECTION_SAFETY_RULES, "Правила безопасности."),
        SECTION_PROFILE_PARAMETERS: _template(
            SECTION_PROFILE_PARAMETERS,
            (
                "Профиль: $system_instruction | $response_style | $target_audience | "
                "$formality_level | $preferred_structure | $forbidden_phrasing_line | "
                "$response_length_line | $additional_constraints_line"
            ),
            (
                "system_instruction",
                "response_style",
                "target_audience",
                "formality_level",
                "preferred_structure",
                "forbidden_phrasing_line",
                "response_length_line",
                "additional_constraints_line",
            ),
        ),
        SECTION_MEMORY: _template(SECTION_MEMORY, "Память: $memory_facts", ("memory_facts",)),
        SECTION_KNOWLEDGE: _template(SECTION_KNOWLEDGE, "Знания: $knowledge_fragments", ("knowledge_fragments",)),
        SECTION_RESPONSE_FORMAT: _template(SECTION_RESPONSE_FORMAT, "Формат ответа."),
    }


def _make_profile(**overrides: object) -> UserProfile:
    created_at = _now()
    defaults: dict[str, object] = {
        "id": uuid4(),
        "name": "Деловой",
        "description": "Кратко и по делу.",
        "system_instruction": "Отвечай кратко и по делу.",
        "response_style": "деловой, лаконичный",
        "target_audience": "широкая аудитория",
        "formality_level": "формальный",
        "preferred_structure": "вывод в начале",
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


def _make_message(role: MessageRole, content: str) -> Message:
    return Message(id=uuid4(), conversation_id=uuid4(), role=role, content=content, created_at=_now())


def _builder(
    templates: dict[str, PromptTemplate] | None = None, budget: int = _HUGE_BUDGET
) -> DeterministicPromptBuilder:
    repository = FakePromptTemplateRepository(templates if templates is not None else _default_templates())
    policy = TokenBudgetPolicy(estimate_size=len)
    return DeterministicPromptBuilder(template_repository=repository, token_budget_policy=policy, budget=budget)


class TestSectionOrder:
    def test_sections_are_in_fixed_order_1_2_3_4_5_8(self) -> None:
        context = PromptContext(
            profile=_make_profile(),
            dialogue_history=[_make_message(MessageRole.USER, "Привет")],
            confirmed_memory_facts=("факт",),
            knowledge_fragments=("фрагмент",),
        )

        result = _builder().build(context)

        assert [section.name for section in result.sections] == [
            SECTION_BASE_INSTRUCTION,
            SECTION_SAFETY_RULES,
            SECTION_PROFILE_PARAMETERS,
            SECTION_MEMORY,
            SECTION_KNOWLEDGE,
            SECTION_RESPONSE_FORMAT,
        ]

    def test_messages_are_not_part_of_sections(self) -> None:
        context = PromptContext(profile=_make_profile(), dialogue_history=[_make_message(MessageRole.USER, "Привет")])

        result = _builder().build(context)

        assert len(result.messages) == 1
        assert all(section.name not in {"dialogue_history", "current_request"} for section in result.sections)


class TestEmptySectionsAreExcluded:
    def test_empty_memory_and_knowledge_do_not_leak_into_system_prompt(self) -> None:
        context = PromptContext(profile=_make_profile(), dialogue_history=[_make_message(MessageRole.USER, "Привет")])

        result = _builder().build(context)

        assert "Память:" not in result.system_prompt
        assert "Знания:" not in result.system_prompt

    def test_non_empty_memory_and_knowledge_are_included(self) -> None:
        context = PromptContext(
            profile=_make_profile(),
            dialogue_history=[_make_message(MessageRole.USER, "Привет")],
            confirmed_memory_facts=("любит краткие ответы",),
            knowledge_fragments=("фрагмент базы знаний",),
        )

        result = _builder().build(context)

        assert "любит краткие ответы" in result.system_prompt
        assert "фрагмент базы знаний" in result.system_prompt


class TestProfileRendering:
    def test_all_descriptive_profile_fields_are_rendered_not_only_system_instruction(self) -> None:
        profile = _make_profile(
            system_instruction="Отвечай точно.",
            response_style="точный, структурированный",
            target_audience="специалисты",
            formality_level="формальный",
            preferred_structure="выводы по пунктам",
            forbidden_phrasing=("возможно", "наверное"),
            response_length_hint="кратко",
            additional_constraints="не используй жаргон",
        )
        context = PromptContext(profile=profile, dialogue_history=[_make_message(MessageRole.USER, "Привет")])

        result = _builder().build(context)

        assert "точный, структурированный" in result.system_prompt
        assert "специалисты" in result.system_prompt
        assert "формальный" in result.system_prompt
        assert "выводы по пунктам" in result.system_prompt
        assert "возможно" in result.system_prompt
        assert "наверное" in result.system_prompt
        assert "кратко" in result.system_prompt
        assert "не используй жаргон" in result.system_prompt

    def test_empty_optional_fields_render_as_empty_not_as_base_instruction_fallback(self) -> None:
        profile = _make_profile(forbidden_phrasing=(), response_length_hint=None, additional_constraints="")
        context = PromptContext(profile=profile, dialogue_history=[_make_message(MessageRole.USER, "Привет")])

        result = _builder().build(context)

        assert "Избегай" not in result.system_prompt
        assert "Ожидаемая длина" not in result.system_prompt
        assert "Дополнительные ограничения" not in result.system_prompt


class TestMessages:
    def test_messages_preserve_dialogue_history_order_and_role_mapping(self) -> None:
        history = [
            _make_message(MessageRole.USER, "Первый вопрос"),
            _make_message(MessageRole.ASSISTANT, "Первый ответ"),
            _make_message(MessageRole.USER, "Текущий запрос"),
        ]
        context = PromptContext(profile=_make_profile(), dialogue_history=history)

        result = _builder().build(context)

        assert [message.content for message in result.messages] == [
            "Первый вопрос",
            "Первый ответ",
            "Текущий запрос",
        ]
        assert [message.role for message in result.messages] == ["user", "assistant", "user"]


class TestRequiredVariableValidation:
    def test_missing_required_variable_raises_application_error_naming_template_and_variable(self) -> None:
        templates = _default_templates()
        templates[SECTION_MEMORY] = _template(SECTION_MEMORY, "Память: $memory_facts", ("memory_facts", "extra_var"))
        context = PromptContext(
            profile=_make_profile(),
            dialogue_history=[_make_message(MessageRole.USER, "Привет")],
            confirmed_memory_facts=("факт",),
        )

        with pytest.raises(ApplicationError) as excinfo:
            _builder(templates=templates).build(context)

        assert SECTION_MEMORY in str(excinfo.value.message)
        assert "extra_var" in str(excinfo.value.message)


class TestDeterminism:
    def test_build_is_deterministic_for_same_input(self) -> None:
        context = PromptContext(
            profile=_make_profile(),
            dialogue_history=[
                _make_message(MessageRole.USER, "Привет"),
                _make_message(MessageRole.ASSISTANT, "Чем помочь?"),
            ],
        )
        builder = _builder()

        first = builder.build(context)
        second = builder.build(context)

        assert first.system_prompt == second.system_prompt
        assert first.messages == second.messages
        assert first.template_versions == second.template_versions


class TestTemplateVersions:
    def test_template_versions_are_populated(self) -> None:
        context = PromptContext(profile=_make_profile(), dialogue_history=[_make_message(MessageRole.USER, "Привет")])

        result = _builder().build(context)

        assert result.template_versions
        assert result.template_versions[SECTION_BASE_INSTRUCTION] == "1.0.0"
        assert result.template_versions[SECTION_PROFILE_PARAMETERS] == "1.0.0"


class TestSystemRulesAlwaysPresent:
    def test_base_instruction_and_safety_rules_present_even_with_minimal_context(self) -> None:
        context = PromptContext(profile=_make_profile(), dialogue_history=[_make_message(MessageRole.USER, "Привет")])

        result = _builder().build(context)

        assert "Базовая инструкция." in result.system_prompt
        assert "Правила безопасности." in result.system_prompt


class TestWithRealSeedTemplates:
    """
    ADR-4.7 DoD: интеграционный тест собирает `PromptContext` для каждого
    из 4 сид-профилей (`alembic/versions/27c4e9f2a103_seed_profile_catalog.py`)
    и проверяет, что отличительные поля каждого профиля присутствуют в
    собранном `system_prompt`, используя реальный `FileTemplateRepository`
    (не fake) — те же шесть сид-шаблонов, что будут загружены в проде.
    """

    def _real_builder(self) -> DeterministicPromptBuilder:
        repository = FileTemplateRepository()
        policy = TokenBudgetPolicy(estimate_size=len)
        return DeterministicPromptBuilder(
            template_repository=repository, token_budget_policy=policy, budget=_HUGE_BUDGET
        )

    @pytest.mark.parametrize(
        ("response_style", "target_audience", "formality_level", "preferred_structure"),
        [
            (
                "точный, структурированный",
                "специалисты и профессионалы",
                "формальный",
                "выводы, риски и ограничения — явно, по пунктам",
            ),
            (
                "тёплый, поддерживающий",
                "широкая аудитория, новички",
                "неформальный",
                "объяснение через примеры, без строгой структуры",
            ),
            (
                "деловой, лаконичный",
                "широкая аудитория",
                "формальный",
                "вывод/рекомендация в начале, затем краткое обоснование",
            ),
            (
                "образный, нестандартный",
                "широкая аудитория, творческие задачи",
                "неформальный",
                "свободная форма, допускаются метафоры и примеры",
            ),
        ],
    )
    def test_each_seed_profile_produces_a_visibly_different_prompt(
        self, response_style: str, target_audience: str, formality_level: str, preferred_structure: str
    ) -> None:
        profile = _make_profile(
            response_style=response_style,
            target_audience=target_audience,
            formality_level=formality_level,
            preferred_structure=preferred_structure,
        )
        context = PromptContext(profile=profile, dialogue_history=[_make_message(MessageRole.USER, "Привет")])

        result = self._real_builder().build(context)

        assert response_style in result.system_prompt
        assert target_audience in result.system_prompt
        assert formality_level in result.system_prompt
        assert preferred_structure in result.system_prompt

    def test_two_different_seed_profiles_yield_different_system_prompts(self) -> None:
        expert = _make_profile(
            response_style="точный, структурированный",
            target_audience="специалисты и профессионалы",
            formality_level="формальный",
            preferred_structure="выводы, риски и ограничения — явно, по пунктам",
        )
        friendly = _make_profile(
            response_style="тёплый, поддерживающий",
            target_audience="широкая аудитория, новички",
            formality_level="неформальный",
            preferred_structure="объяснение через примеры, без строгой структуры",
        )
        history = [_make_message(MessageRole.USER, "Привет")]

        builder = self._real_builder()
        expert_prompt = builder.build(PromptContext(profile=expert, dialogue_history=history)).system_prompt
        friendly_prompt = builder.build(PromptContext(profile=friendly, dialogue_history=history)).system_prompt

        assert expert_prompt != friendly_prompt
