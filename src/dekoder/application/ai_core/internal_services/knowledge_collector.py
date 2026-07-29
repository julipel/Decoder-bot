"""
Внутренний коллаборатор ai_core — вызывает RAG только если режим Skill
требует/допускает (docs/versions/05, §9). Работает с VectorRepository
напрямую (домен, не View DTO) — как и MemoryCollector, внутренние
коллабораторы оперируют доменными сущностями, Query/View — для внешних
потребителей (Telegram/Admin UI), а не для сборки ExecutionContext.
"""

from __future__ import annotations

from dekoder.application.rag.ports import VectorRepository
from dekoder.domain.rag.fragment import KnowledgeFragment
from dekoder.domain.skills.skill import ContentSkill


class KnowledgeCollector:
    def __init__(self, vector_repository: VectorRepository) -> None:
        self._vector_repository = vector_repository

    def collect(self, query_text: str, skill: ContentSkill) -> list[KnowledgeFragment]:
        raise NotImplementedError
