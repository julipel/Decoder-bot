"""Команды, которые Telegram Adapter вызывает напрямую на AI Core (docs/versions/05, §4)."""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.shared.domain.identifiers import SessionId, UserId


@dataclass(frozen=True)
class GenerateContentCommand:
    user_id: UserId
    session_id: SessionId


@dataclass(frozen=True)
class AnswerKnowledgeQuestionCommand:
    user_id: UserId
    question_text: str


@dataclass(frozen=True)
class RegenerateCommand:
    user_id: UserId
    session_id: SessionId
