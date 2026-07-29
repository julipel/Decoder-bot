from __future__ import annotations

from dekoder.application.model_gateway.ports import (
    ModelGateway,
    ModelGatewayRequest,
    ModelGatewayResult,
)


class OpenAiLLMAdapter(ModelGateway):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def generate(self, request: ModelGatewayRequest) -> ModelGatewayResult:
        raise NotImplementedError
