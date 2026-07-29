from __future__ import annotations

from dekoder.application.session.commands import SubmitUserInputCommand
from dekoder.application.session.ports import SessionRepository
from dekoder.application.session.queries import GenerationSessionView


class SubmitUserInputUseCase:
    def __init__(self, session_repository: SessionRepository) -> None:
        self._session_repository = session_repository

    def execute(self, command: SubmitUserInputCommand) -> GenerationSessionView:
        raise NotImplementedError
