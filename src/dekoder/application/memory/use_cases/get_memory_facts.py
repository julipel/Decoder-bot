from __future__ import annotations

from dekoder.application.memory.ports import MemoryRepository
from dekoder.application.memory.queries import GetMemoryFactsQuery, MemoryFactView


class GetMemoryFactsUseCase:
    def __init__(self, memory_repository: MemoryRepository) -> None:
        self._memory_repository = memory_repository

    def execute(self, query: GetMemoryFactsQuery) -> list[MemoryFactView]:
        raise NotImplementedError
