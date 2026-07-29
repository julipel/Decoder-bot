from __future__ import annotations

from dekoder.application.memory.commands import ConfirmMemoryFactCommand
from dekoder.application.memory.ports import MemoryRepository
from dekoder.domain.memory.fact import MemoryFact


class ConfirmMemoryFactUseCase:
    """Может завершиться MemoryConflict, если черновик истёк или отсутствует (05, §12)."""

    def __init__(self, memory_repository: MemoryRepository) -> None:
        self._memory_repository = memory_repository

    def execute(self, command: ConfirmMemoryFactCommand) -> MemoryFact:
        raise NotImplementedError
