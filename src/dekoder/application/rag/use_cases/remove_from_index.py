from __future__ import annotations

from dekoder.application.rag.commands import RemoveFromIndexCommand
from dekoder.application.rag.ports import VectorRepository


class RemoveFromIndexUseCase:
    def __init__(self, vector_repository: VectorRepository) -> None:
        self._vector_repository = vector_repository

    def execute(self, command: RemoveFromIndexCommand) -> None:
        raise NotImplementedError
