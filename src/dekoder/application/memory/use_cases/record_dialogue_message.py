from __future__ import annotations

from dekoder.application.memory.commands import RecordDialogueMessageCommand
from dekoder.application.memory.ports import MemoryRepository


class RecordDialogueMessageUseCase:
    def __init__(self, memory_repository: MemoryRepository) -> None:
        self._memory_repository = memory_repository

    def execute(self, command: RecordDialogueMessageCommand) -> None:
        raise NotImplementedError
