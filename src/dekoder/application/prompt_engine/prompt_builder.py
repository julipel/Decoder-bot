"""
Конкретная реализация PromptBuilder живёт здесь, не в infrastructure/ —
Prompt Engine не имеет I/O, это чистая функция (docs/versions/02, §6).
"""

from __future__ import annotations

from dekoder.application.prompt_engine.ports import PromptBuilder
from dekoder.shared.application.execution_context import ExecutionContext
from dekoder.shared.domain.value_objects import Prompt


class DeterministicPromptBuilder(PromptBuilder):
    """
    Порядок приоритета источников (02, §6): системные ограничения →
    профиль → Skill → тип контента → пользовательский ввод → RAG-контекст
    → подтверждённая память → история сценария.
    """

    def build(self, context: ExecutionContext) -> Prompt:
        raise NotImplementedError
