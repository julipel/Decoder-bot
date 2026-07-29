from __future__ import annotations

from dekoder.application.session.commands import StartGenerationSessionCommand
from dekoder.application.session.ports import SessionRepository
from dekoder.application.session.queries import GenerationSessionView


class StartGenerationSessionUseCase:
    """Гарантирует не более одной активной сессии на пользователя (04, §8)."""

    def __init__(self, session_repository: SessionRepository) -> None:
        self._session_repository = session_repository

    def execute(self, command: StartGenerationSessionCommand) -> GenerationSessionView:
        raise NotImplementedError
