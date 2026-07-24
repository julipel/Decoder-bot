"""Реализация LLMPort поверх YandexGPT. Выбирается через LLM_PROVIDER=yandex (основной поставщик)."""

from __future__ import annotations

from dekoder.modules.llm.application.ports import LLMPort, LLMRequestContext, LLMResponse


class YandexGptLLMAdapter(LLMPort):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def complete(self, context: LLMRequestContext) -> LLMResponse:
        raise NotImplementedError
