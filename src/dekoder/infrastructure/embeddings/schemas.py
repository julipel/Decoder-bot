"""Схемы внешнего JSON-контракта OpenAI Embeddings API — тот же приём, что и `infrastructure/llm/schemas.py`."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OpenAiEmbeddingRequest(BaseModel):
    model: str
    input: list[str]


class OpenAiEmbeddingItem(BaseModel):
    index: int
    embedding: list[float]


class OpenAiEmbeddingResponse(BaseModel):
    data: list[OpenAiEmbeddingItem] = Field(default_factory=list)
    model: str | None = None
