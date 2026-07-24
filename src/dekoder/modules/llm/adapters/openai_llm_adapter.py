"""Реализация LLMPort поверх OpenAI. Выбирается через LLM_PROVIDER=openai (резервный поставщик, docs/01, §4.2)."""

from __future__ import annotations

from dekoder.modules.llm.application.ports import LLMPort, LLMRequestContext, LLMResponse


class OpenAiLLMAdapter(LLMPort):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def complete(self, context: LLMRequestContext) -> LLMResponse:
        raise NotImplementedError
