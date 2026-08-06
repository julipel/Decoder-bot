"""
GenerateContentUseCase — основной сценарий генерации (docs/versions/05, §13,
диаграмма «Генерация ответа»): Session → Skill → Model → Execution Context
→ Prompt → Model Gateway → Response.
"""

from __future__ import annotations

from dekoder.application.ai_core.commands import GenerateContentCommand
from dekoder.application.ai_core.internal_services.execution_context_builder import (
    ExecutionContextBuilder,
)
from dekoder.application.ai_core.internal_services.model_selector import ModelSelector
from dekoder.application.ai_core.internal_services.response_formatter import ResponseFormatter
from dekoder.application.ai_core.internal_services.session_coordinator import SessionCoordinator
from dekoder.application.ai_core.internal_services.skill_resolver import SkillResolver
from dekoder.application.ai_core.responses import GenerationResult
from dekoder.application.model_gateway.ports import ModelGateway
from dekoder.shared.utils.correlation import CorrelationIdGenerator


class GenerateContentUseCase:
    def __init__(
        self,
        session_coordinator: SessionCoordinator,
        skill_resolver: SkillResolver,
        model_selector: ModelSelector,
        execution_context_builder: ExecutionContextBuilder,
        model_gateway: ModelGateway,
        response_formatter: ResponseFormatter,
        correlation_id_generator: CorrelationIdGenerator,
    ) -> None:
        self._session_coordinator = session_coordinator
        self._skill_resolver = skill_resolver
        self._model_selector = model_selector
        self._execution_context_builder = execution_context_builder
        self._model_gateway = model_gateway
        self._response_formatter = response_formatter
        self._correlation_id_generator = correlation_id_generator

    def execute(self, command: GenerateContentCommand) -> GenerationResult:
        raise NotImplementedError
