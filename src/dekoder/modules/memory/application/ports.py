"""
Порты сервиса памяти (docs/02, §7).

DialogueHistoryPort обслуживает только историю диалога. FactRepositoryPort
сознательно объединяет черновики и подтверждённые факты одним портом
(а не двумя) — это один и тот же жизненный цикл записи («черновик →
подтверждение»), а не два независимых хранилища.
"""

from __future__ import annotations

from typing import Protocol

from dekoder.modules.memory.domain.dialogue_message import DialogueMessage
from dekoder.modules.memory.domain.fact import Fact
from dekoder.modules.memory.domain.fact_draft import FactDraft
from dekoder.shared.domain.identifiers import (
    ChatId,
    CorrelationId,
    DialogueMessageId,
    FactDraftId,
    FactId,
    UserId,
)


class DialogueHistoryPort(Protocol):
    """
    История диалога как последовательность отдельных реплик (docs/01, §4.4).

    Реплика пользователя и ответ ассистента — раздельные записи: одна
    запись истории не превращается из сообщения пользователя в пару
    «запрос + ответ» (docs/03, §16).
    """

    def get_recent(self, dialogue_id: ChatId, limit: int) -> list[DialogueMessage]: ...

    def record_user_message(self, dialogue_id: ChatId, text: str, correlation_id: CorrelationId) -> DialogueMessage:
        """Создаёт новую запись реплики пользователя со статусом received (docs/02, §8)."""
        ...

    def record_assistant_message(
        self, dialogue_id: ChatId, text: str, correlation_id: CorrelationId
    ) -> DialogueMessage:
        """Создаёт новую запись ответа ассистента — отдельную от реплики пользователя."""
        ...

    def mark_request_completed(self, user_message_id: DialogueMessageId) -> None:
        """Переводит статус реплики пользователя в completed."""
        ...

    def mark_request_failed(self, user_message_id: DialogueMessageId) -> None:
        """Переводит статус реплики пользователя в failed при ошибке обработки."""
        ...


class FactRepositoryPort(Protocol):
    """Черновики и подтверждённые факты пользователя (docs/01, §4.4)."""

    def stage_draft(self, user_id: UserId, text: str) -> FactDraft: ...

    def confirm_draft(self, draft_id: FactDraftId) -> Fact: ...

    def list_confirmed(self, user_id: UserId) -> list[Fact]: ...

    def forget(self, user_id: UserId, fact_id: FactId) -> None: ...
