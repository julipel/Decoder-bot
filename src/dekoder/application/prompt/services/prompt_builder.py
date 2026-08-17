"""
`DeterministicPromptBuilder` — конкретная реализация `PromptBuilder`
(Sprint 4, задача S4-05, ADR-4.1/4.2/4.3/4.7/4.9), по аналогии с тем, как
`SQLAlchemyProfileRepository` реализует `ProfileRepository`
(`infrastructure/persistence/profile_repository.py`).

`build()` — синхронный, без I/O (ADR-4.1/4.8): рендерит секции 1,2,3,8
из шаблонов `PromptTemplateRepository` через `string.Template.
substitute()`, с явной проверкой обязательных переменных до подстановки
(ADR-4.2/4.9 — приватный метод `_substitute` этого сервиса, не отдельный
класс `PromptValidationService`); секции 4/5 рендерит напрямую из
`context.confirmed_memory_facts`/`knowledge_fragments` (пусто в Sprint 4
→ пустая секция, тем же кодовым путём, который позже будет рендерить
реальный контент памяти/RAG, ADR-4.3); строит `messages` из
`context.dialogue_history` (role-mapping, переехавший из
`ProcessUserMessage`, ADR-4.1); вызывает `TokenBudgetPolicy.enforce(...)`
последним шагом (ADR-4.5) — единственная точка вызова во всём проекте.

Не обращается к `ProfileRepository`/`ConversationRepositoriesFactory` —
только к уже переданному `PromptContext` и внедрённому через конструктор
`PromptTemplateRepository` (ADR-4.7).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from string import Template

from dekoder.application.conversation.dto import LLMMessage
from dekoder.application.prompt.ports import PromptTemplateRepository
from dekoder.domain.prompt.entities import PromptTemplate
from dekoder.domain.prompt.policies import TokenBudgetPolicy
from dekoder.domain.prompt.value_objects import (
    SECTION_BASE_INSTRUCTION,
    SECTION_KNOWLEDGE,
    SECTION_MEMORY,
    SECTION_PROFILE_PARAMETERS,
    SECTION_RESPONSE_FORMAT,
    SECTION_SAFETY_RULES,
    PromptBuildResult,
    PromptContext,
    PromptSection,
)
from dekoder.shared.errors import ApplicationError


class DeterministicPromptBuilder:
    """
    Единственная реализация `PromptBuilder` (`application/prompt/
    ports.py`) в проекте — структурное соответствие протоколу
    (`Protocol`, не `@runtime_checkable`), без явного наследования.
    """

    def __init__(
        self,
        template_repository: PromptTemplateRepository,
        token_budget_policy: TokenBudgetPolicy,
        budget: int,
    ) -> None:
        self._templates = template_repository
        self._token_budget_policy = token_budget_policy
        self._budget = budget

    def build(self, context: PromptContext) -> PromptBuildResult:
        template_versions: dict[str, str] = {}

        sections: Sequence[PromptSection] = [
            self._render_static_section(SECTION_BASE_INSTRUCTION, template_versions),
            self._render_static_section(SECTION_SAFETY_RULES, template_versions),
            self._render_profile_section(context, template_versions),
            self._render_placeholder_section(
                SECTION_MEMORY, "memory_facts", context.confirmed_memory_facts, template_versions
            ),
            self._render_placeholder_section(
                SECTION_KNOWLEDGE, "knowledge_fragments", context.knowledge_fragments, template_versions
            ),
            self._render_static_section(SECTION_RESPONSE_FORMAT, template_versions),
        ]
        messages: Sequence[LLMMessage] = [
            LLMMessage(role=message.role.value, content=message.content) for message in context.dialogue_history
        ]

        sections, messages = self._token_budget_policy.enforce(sections, messages, self._budget)

        system_prompt = "\n\n".join(section.text.strip() for section in sections if section.text.strip())

        return PromptBuildResult(
            system_prompt=system_prompt,
            messages=messages,
            template_versions=template_versions,
            sections=sections,
        )

    def _render_static_section(self, name: str, template_versions: dict[str, str]) -> PromptSection:
        """Секции 1, 2, 8 — без пользовательских переменных (пустой `variables`)."""
        template = self._templates.get(name)
        template_versions[template.id] = template.version
        text = self._substitute(template, {})
        return PromptSection(name=name, text=text)

    def _render_profile_section(self, context: PromptContext, template_versions: dict[str, str]) -> PromptSection:
        """
        Секция 3 — рендерит ВСЕ описательные поля `UserProfile`, не
        только `system_instruction` (ADR-4.7): `response_style`,
        `target_audience`, `formality_level`, `preferred_structure`,
        `forbidden_phrasing` (объединённые в отдельную строку),
        `response_length_hint`/`additional_constraints` — только если
        заданы (пустая строка иначе, отсутствующая строка не подставляется
        как «fallback на базовую инструкцию» — эту роль вместо этого
        безусловно играет секция 1, ADR-4.7).

        `preferred_model` намеренно не используется — выбор модели вне
        объёма Sprint 4 (Этап 9, ADR-4.7).
        """
        profile = context.profile
        variables = {
            "system_instruction": profile.system_instruction,
            "response_style": profile.response_style,
            "target_audience": profile.target_audience,
            "formality_level": profile.formality_level,
            "preferred_structure": profile.preferred_structure,
            "forbidden_phrasing_line": (
                f"Избегай таких формулировок: {', '.join(profile.forbidden_phrasing)}."
                if profile.forbidden_phrasing
                else ""
            ),
            "response_length_line": (
                f"Ожидаемая длина ответа: {profile.response_length_hint}" if profile.response_length_hint else ""
            ),
            "additional_constraints_line": (
                f"Дополнительные ограничения: {profile.additional_constraints}"
                if profile.additional_constraints.strip()
                else ""
            ),
        }
        template = self._templates.get(SECTION_PROFILE_PARAMETERS)
        template_versions[template.id] = template.version
        text = self._substitute(template, variables)
        return PromptSection(name=SECTION_PROFILE_PARAMETERS, text=text)

    def _render_placeholder_section(
        self,
        name: str,
        variable_name: str,
        items: Sequence[str],
        template_versions: dict[str, str],
    ) -> PromptSection:
        """
        Секции 4/5 (память/RAG, ADR-4.3) — один и тот же код-путь и для
        Sprint 4 (`items` всегда пуст → пустая секция, без обращения к
        `string.Template`), и для будущих Этапов 7/8 (непустой `items` →
        реальный рендер через шаблон). Шаблон всё равно загружается и
        версионируется (`template_versions`) даже когда секция в итоге
        пуста — он был выбран для этой секции, это факт сборки, полезный
        для аудита (ADR-4.6), а не только для содержательного рендера.
        """
        template = self._templates.get(name)
        template_versions[template.id] = template.version
        if not items:
            return PromptSection(name=name, text="")
        text = self._substitute(template, {variable_name: "\n".join(items)})
        return PromptSection(name=name, text=text)

    @staticmethod
    def _substitute(template: PromptTemplate, variables: Mapping[str, str]) -> str:
        """
        Проверяет `template.required_variables` против ключей `variables`
        ДО вызова `.substitute()` (ADR-4.2/4.9) — при отсутствии хотя бы
        одной поднимает `ApplicationError`, называющую и шаблон, и
        недостающие переменные, а не голый `KeyError`.
        """
        missing = [variable for variable in template.required_variables if variable not in variables]
        if missing:
            raise ApplicationError(
                message=(
                    f"Шаблон промпта '{template.id}' требует переменные {missing}, но они не были переданы при сборке"
                ),
                user_message="Произошла внутренняя ошибка конфигурации ассистента.",
                metadata={"template_id": template.id, "missing_variables": missing},
            )
        return Template(template.text).substitute(variables)
