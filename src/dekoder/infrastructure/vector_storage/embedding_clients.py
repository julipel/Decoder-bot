"""
Приватные клиенты вычисления эмбеддингов — деталь реализации
QdrantVectorRepository, без собственного порта (docs/versions/05, §8:
явный отказ от EmbeddingGateway/EmbeddingPort в v2).
"""

from __future__ import annotations


class OpenAiEmbeddingClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError


class YandexGptEmbeddingClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError
