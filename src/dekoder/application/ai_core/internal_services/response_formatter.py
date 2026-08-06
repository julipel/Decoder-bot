"""
Внутренний коллаборатор ai_core — единственный, кто строит Response DTO
из результата ModelGateway (docs/versions/05, §9, §11).
"""

from __future__ import annotations

from dekoder.application.ai_core.responses import GenerationResult
from dekoder.application.model_gateway.ports import ModelGatewayResult
from dekoder.shared.domain.value_objects import ContentType


class ResponseFormatter:
    def format_generation_result(
        self, result: ModelGatewayResult, content_type: ContentType | None
    ) -> GenerationResult:
        raise NotImplementedError
