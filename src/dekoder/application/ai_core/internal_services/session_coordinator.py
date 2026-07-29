"""Внутренний коллаборатор ai_core — вызывается только отсюда, не является портом (docs/versions/05, §9)."""

from __future__ import annotations

from dekoder.application.session.ports import SessionRepository
from dekoder.domain.session.session import GenerationSession
from dekoder.shared.domain.identifiers import SessionId


class SessionCoordinator:
    """Читает/обновляет сессию; распознаёт устаревшее состояние (SessionExpired, 05 §12)."""

    def __init__(self, session_repository: SessionRepository) -> None:
        self._session_repository = session_repository

    def get_or_fail(self, session_id: SessionId) -> GenerationSession:
        raise NotImplementedError
