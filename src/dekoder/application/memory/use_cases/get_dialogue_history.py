from __future__ import annotations

from dekoder.application.memory.ports import MemoryRepository
from dekoder.application.memory.queries import DialogueEntryView, GetDialogueHistoryQuery


class GetDialogueHistoryUseCase:
    def __init__(self, memory_repository: MemoryRepository) -> None:
        self._memory_repository = memory_repository

    def execute(self, query: GetDialogueHistoryQuery) -> list[DialogueEntryView]:
        raise NotImplementedError
