"""Реализация EmbeddingPort поверх YandexGPT. Выбирается через EMBEDDING_PROVIDER=yandex."""

from __future__ import annotations

from dekoder.modules.search.application.ports import EmbeddingPort


class YandexGptEmbeddingAdapter(EmbeddingPort):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError
