"""Внутренний коллаборатор ai_core — единственный вызывающий PromptBuilder (docs/versions/05, §9, §11)."""

from __future__ import annotations

from dekoder.application.prompt_engine.ports import PromptBuilder
from dekoder.shared.application.execution_context import ExecutionContext
from dekoder.shared.domain.value_objects import Prompt


class PromptAssembler:
    def __init__(self, prompt_builder: PromptBuilder) -> None:
        self._prompt_builder = prompt_builder

    def assemble(self, context: ExecutionContext) -> Prompt:
        raise NotImplementedError
