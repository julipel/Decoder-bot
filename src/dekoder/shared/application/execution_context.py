"""
ExecutionContext (docs/versions/02, §7; docs/versions/04, §11) — не Entity,
не персистится; собирается application/ai_core/ непосредственно перед
вызовом PromptBuilder и потребляется только им.

Как и v1 ConversationContext, это документированное исключение из
изоляции shared/application/: DTO по своей природе объединяет сущности
нескольких модулей (profile/skills/session/memory/rag), поэтому вынесен
из ai_core — иначе потребители импортировали бы его из modules/ai_core
напрямую (docs/versions/03, §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dekoder.domain.memory.dialogue_entry import DialogueEntry
from dekoder.domain.memory.fact import MemoryFact
from dekoder.domain.rag.fragment import KnowledgeFragment
from dekoder.domain.session.session import GenerationSession
from dekoder.domain.skills.skill import ContentSkill
from dekoder.shared.domain.identifiers import CorrelationId
from dekoder.shared.domain.value_objects import ContentType, GenerationType


@dataclass(frozen=True)
class ExecutionContext:
    correlation_id: CorrelationId
    skill: ContentSkill
    generation_type: GenerationType
    content_type: ContentType | None
    session: GenerationSession
    user_input: dict[str, str]
    confirmed_facts: list[MemoryFact]
    dialogue_history: list[DialogueEntry]
    knowledge_fragments: list[KnowledgeFragment] = field(default_factory=list)
