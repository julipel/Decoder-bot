"""
Общие идентификаторы предметной области.

Единая точка правды для типов идентификаторов, пересекающих границы
модулей (например, DocumentId нужен и Knowledge Base, и Search), — чтобы
модули не были вынуждены импортировать чужие domain-пакеты только ради
типа идентификатора.
"""

from __future__ import annotations

from typing import NewType

UserId = NewType("UserId", str)
ChatId = NewType("ChatId", str)
CorrelationId = NewType("CorrelationId", str)

ProfileId = NewType("ProfileId", str)
DialogueMessageId = NewType("DialogueMessageId", str)
FactId = NewType("FactId", str)
FactDraftId = NewType("FactDraftId", str)

DocumentId = NewType("DocumentId", str)
CaseId = NewType("CaseId", str)
FragmentId = NewType("FragmentId", str)
