"""
Внутренний коллаборатор ai_core — единственный, кто строит Response DTO
из результата ModelGateway (docs/versions/05, §9, §11).
"""

from __future__ import annotations

from dekoder.application.ai_core.responses import GenerationResult, KnowledgeAnswerResult
from dekoder.application.model_gateway.ports import ModelGatewayResult
from dekoder.shared.domain.value_objects import ContentType


class ResponseFormatter:
    def format_generation_result(
        self, result: ModelGatewayResult, content_type: ContentType | None
    ) -> GenerationResult:
        raise NotImplementedError

    def format_knowledge_answer(self, result: ModelGatewayResult, used_rag: bool) -> KnowledgeAnswerResult:
        raise NotImplementedError
