"""Внутренний коллаборатор ai_core — не решает, какие факты применимы к генерации (docs/versions/05, §9)."""

from __future__ import annotations

from dekoder.application.memory.ports import MemoryRepository
from dekoder.domain.memory.dialogue_entry import DialogueEntry
from dekoder.domain.memory.fact import MemoryFact
from dekoder.shared.domain.identifiers import UserId


class MemoryCollector:
    def __init__(self, memory_repository: MemoryRepository) -> None:
        self._memory_repository = memory_repository

    def collect(self, user_id: UserId, history_window: int) -> tuple[list[DialogueEntry], list[MemoryFact]]:
        raise NotImplementedError
