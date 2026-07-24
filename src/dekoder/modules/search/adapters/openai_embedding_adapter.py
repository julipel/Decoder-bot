"""Реализация EmbeddingPort поверх OpenAI. Выбирается через EMBEDDING_PROVIDER=openai."""

from __future__ import annotations

from dekoder.modules.search.application.ports import EmbeddingPort


class OpenAiEmbeddingAdapter(EmbeddingPort):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError
