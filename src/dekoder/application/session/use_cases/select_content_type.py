from __future__ import annotations

from dekoder.application.session.commands import SelectContentTypeCommand
from dekoder.application.session.ports import SessionRepository
from dekoder.application.session.queries import GenerationSessionView


class SelectContentTypeUseCase:
    def __init__(self, session_repository: SessionRepository) -> None:
        self._session_repository = session_repository

    def execute(self, command: SelectContentTypeCommand) -> GenerationSessionView:
        raise NotImplementedError
