from __future__ import annotations

from dekoder.application.memory.commands import ForgetMemoryFactCommand
from dekoder.application.memory.ports import MemoryRepository


class ForgetMemoryFactUseCase:
    def __init__(self, memory_repository: MemoryRepository) -> None:
        self._memory_repository = memory_repository

    def execute(self, command: ForgetMemoryFactCommand) -> None:
        raise NotImplementedError
