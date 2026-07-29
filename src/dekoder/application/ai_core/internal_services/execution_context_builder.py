"""Внутренний коллаборатор ai_core — собирает ExecutionContext, сам не обращается к портам (docs/versions/05, §9)."""

from __future__ import annotations

from dekoder.domain.memory.dialogue_entry import DialogueEntry
from dekoder.domain.memory.fact import MemoryFact
from dekoder.domain.profile.profile import AuthorProfile
from dekoder.domain.rag.fragment import KnowledgeFragment
from dekoder.domain.session.session import GenerationSession
from dekoder.domain.skills.skill import ContentSkill
from dekoder.shared.application.execution_context import ExecutionContext
from dekoder.shared.domain.identifiers import CorrelationId
from dekoder.shared.domain.value_objects import ContentType, GenerationType


class ExecutionContextBuilder:
    def build(
        self,
        correlation_id: CorrelationId,
        profile: AuthorProfile,
        skill: ContentSkill,
        generation_type: GenerationType,
        content_type: ContentType | None,
        session: GenerationSession,
        user_input: dict[str, str],
        confirmed_facts: list[MemoryFact],
        dialogue_history: list[DialogueEntry],
        knowledge_fragments: list[KnowledgeFragment],
    ) -> ExecutionContext:
        raise NotImplementedError
