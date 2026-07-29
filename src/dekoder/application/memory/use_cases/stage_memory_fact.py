from __future__ import annotations

from dekoder.application.memory.commands import StageMemoryFactCommand
from dekoder.application.memory.ports import MemoryRepository
from dekoder.domain.memory.fact_draft import MemoryFactDraft
from dekoder.shared.utils.clock import Clock


class StageMemoryFactUseCase:
    """Заменяет существующий активный черновик, если был (не более одного на пользователя — 04, §8)."""

    def __init__(self, memory_repository: MemoryRepository, clock: Clock) -> None:
        self._memory_repository = memory_repository
        self._clock = clock

    def execute(self, command: StageMemoryFactCommand) -> MemoryFactDraft:
        raise NotImplementedError
