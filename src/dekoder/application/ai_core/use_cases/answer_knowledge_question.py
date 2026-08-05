"""
AnswerKnowledgeQuestionUseCase — ответ по базе знаний (docs/versions/05,
§13): без выбора Skill/типа/модели, Memory + RAG → Execution Context →
Prompt → Model Gateway (TEXT).
"""

from __future__ import annotations

from dekoder.application.ai_core.commands import AnswerKnowledgeQuestionCommand
from dekoder.application.ai_core.internal_services.execution_context_builder import (
    ExecutionContextBuilder,
)
from dekoder.application.ai_core.internal_services.knowledge_collector import KnowledgeCollector
from dekoder.application.ai_core.internal_services.response_formatter import ResponseFormatter
from dekoder.application.ai_core.responses import KnowledgeAnswerResult
from dekoder.application.model_gateway.ports import ModelGateway
from dekoder.shared.utils.correlation import CorrelationIdGenerator


class AnswerKnowledgeQuestionUseCase:
    def __init__(
        self,
        knowledge_collector: KnowledgeCollector,
        execution_context_builder: ExecutionContextBuilder,
        model_gateway: ModelGateway,
        response_formatter: ResponseFormatter,
        correlation_id_generator: CorrelationIdGenerator,
    ) -> None:
        self._knowledge_collector = knowledge_collector
        self._execution_context_builder = execution_context_builder
        self._model_gateway = model_gateway
        self._response_formatter = response_formatter
        self._correlation_id_generator = correlation_id_generator

    def execute(self, command: AnswerKnowledgeQuestionCommand) -> KnowledgeAnswerResult:
        raise NotImplementedError
