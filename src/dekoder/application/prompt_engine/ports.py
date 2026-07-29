"""PromptBuilder — детерминированное построение инструкции из Execution Context (docs/versions/02, §6)."""

from __future__ import annotations

from typing import Protocol

from dekoder.shared.application.execution_context import ExecutionContext
from dekoder.shared.domain.value_objects import Prompt


class PromptBuilder(Protocol):
    def build(self, context: ExecutionContext) -> Prompt: ...
