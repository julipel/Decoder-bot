"""Response DTO для команд AI Core (docs/versions/05, §6)."""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.shared.domain.value_objects import ContentType


@dataclass(frozen=True)
class GenerationResult:
    status: str
    content_type: ContentType | None
    generated_text: str | None
    generated_image_ref: str | None
    provider_used: str | None
    model_used: str | None
    duration: float | None
    error: str | None


@dataclass(frozen=True)
class KnowledgeAnswerResult:
    status: str
    answer_text: str | None
    used_rag: bool
    provider_used: str | None
    model_used: str | None
    error: str | None
