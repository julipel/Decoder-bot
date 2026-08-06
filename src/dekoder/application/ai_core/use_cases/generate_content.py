"""
GenerateContentUseCase — основной сценарий генерации (docs/versions/05, §13,
диаграмма «Генерация ответа»): Session → Skill → Execution Context → Prompt
→ Response.
"""

from __future__ import annotations

from dekoder.application.ai_core.commands import GenerateContentCommand
from dekoder.application.ai_core.internal_services.execution_context_builder import (
    ExecutionContextBuilder,
)
from dekoder.application.ai_core.internal_services.session_coordinator import SessionCoordinator
from dekoder.application.ai_core.internal_services.skill_resolver import SkillResolver
from dekoder.application.ai_core.responses import GenerationResult
from dekoder.shared.utils.correlation import CorrelationIdGenerator


class GenerateContentUseCase:
    def __init__(
        self,
        session_coordinator: SessionCoordinator,
        skill_resolver: SkillResolver,
        execution_context_builder: ExecutionContextBuilder,
        correlation_id_generator: CorrelationIdGenerator,
    ) -> None:
        self._session_coordinator = session_coordinator
        self._skill_resolver = skill_resolver
        self._execution_context_builder = execution_context_builder
        self._correlation_id_generator = correlation_id_generator

    def execute(self, command: GenerateContentCommand) -> GenerationResult:
        raise NotImplementedError
