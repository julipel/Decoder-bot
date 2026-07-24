"""
Единый контекст запроса к языковой модели (docs/01, §4.2).

Источники собраны в порядке приоритета: системные ограничения → профиль
→ документы БЗ (включая кейсы) → подтверждённые факты → история диалога
→ общие знания модели.

ConversationContext — не внутреннее состояние AI Core, а контракт,
которым пользуются несколько сторон: build_conversation_context.py
(наполняет), generate_assistant_response.py (потребляет), в будущем —
дополнительные driving adapters (например, голосовой канал) и тесты.
Поэтому он вынесен в shared/application, а не в modules/ai_core/application
— иначе со временем эти стороны начали бы импортировать его напрямую из
ai_core, создавая зависимость вида «llm → ai_core» или «voice → ai_core»,
которой в архитектуре (docs/02) нет. AI Core, LLM и тесты зависят только
от shared, а не друг от друга.

shared/domain остаётся не зависящим ни от одного модуля (см. docs/03, §4).
Этот файл в shared/application — осознанное исключение из этого правила:
контракт по своей природе объединяет несколько bounded context'ов (Profile,
Fact, DialogueMessage, Fragment), поэтому зависит от их domain-пакетов —
но никогда от их application/adapters.
"""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.modules.memory.domain.dialogue_message import DialogueMessage
from dekoder.modules.memory.domain.fact import Fact
from dekoder.modules.profile.domain.profile import Profile
from dekoder.modules.search.domain.fragment import Fragment


@dataclass(frozen=True)
class ConversationContext:
    """Источники контекста, уже упорядоченные по приоритету (docs/01, §4.2)."""

    profile: Profile
    knowledge_fragments: list[Fragment]
    confirmed_facts: list[Fact]
    dialogue_history: list[DialogueMessage]
