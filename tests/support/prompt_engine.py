"""
Тестовый helper для сборки реального `PromptBuilder` (Sprint 4, задача
S4-07) — используется тестами `ProcessUserMessage`/Telegram-хендлеров/
e2e-сценариев, которым нужен РАБОТАЮЩИЙ Prompt Engine (реальные сид-
шаблоны `infrastructure/prompts/templates/`, реальная `TokenBudgetPolicy`),
но не важно точное содержимое собранного `system_prompt` — в отличие от
`tests/unit/application/test_prompt_builder.py`/`test_token_budget.py`,
где именно содержимое и есть предмет проверки.

Бюджет — заведомо огромный по умолчанию, чтобы `TokenBudgetPolicy` не
обрезала историю в тестах, не проверяющих обрезание объёма (это отдельно
проверяют `tests/unit/application/test_token_budget.py` и e2e-сценарий
длинного диалога, задача S4-08).

Не fake — реальный `DeterministicPromptBuilder` + `FileTemplateRepository`
+ `TokenBudgetPolicy`, тот же путь, что и в проде (`bootstrap/
container.py`). Никакого SQLAlchemy/HTTP — файлы шаблонов читаются один
раз при построении (ADR-4.2), как и в проде.
"""

from __future__ import annotations

from dekoder.application.prompt.services.prompt_builder import DeterministicPromptBuilder
from dekoder.application.prompt.services.token_budget import estimate_size
from dekoder.domain.prompt.policies import TokenBudgetPolicy
from dekoder.infrastructure.prompts.file_template_repository import FileTemplateRepository

_GENEROUS_TEST_BUDGET = 1_000_000


def make_test_prompt_builder(budget: int = _GENEROUS_TEST_BUDGET) -> DeterministicPromptBuilder:
    """Собирает `DeterministicPromptBuilder` поверх реальных сид-шаблонов, с просторным бюджетом по умолчанию."""
    return DeterministicPromptBuilder(
        template_repository=FileTemplateRepository(),
        token_budget_policy=TokenBudgetPolicy(estimate_size=estimate_size),
        budget=budget,
    )
