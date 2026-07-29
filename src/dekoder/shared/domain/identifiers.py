"""
Общие идентификаторы предметной области (v2.0).

Единая точка правды для типов идентификаторов, пересекающих границы
модулей, — чтобы модули не были вынуждены импортировать чужие
domain-пакеты только ради типа идентификатора (docs/versions/03, §4).
"""

from __future__ import annotations

from typing import NewType

UserId = NewType("UserId", str)
CorrelationId = NewType("CorrelationId", str)

ProfileId = NewType("ProfileId", str)
SkillId = NewType("SkillId", str)
SessionId = NewType("SessionId", str)
ModelId = NewType("ModelId", str)

DialogueEntryId = NewType("DialogueEntryId", str)
DraftId = NewType("DraftId", str)
FactId = NewType("FactId", str)

DocumentId = NewType("DocumentId", str)
CaseId = NewType("CaseId", str)
FragmentId = NewType("FragmentId", str)

AuditRecordId = NewType("AuditRecordId", str)
