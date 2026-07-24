"""
Сборка единого контекста запроса (docs/01, §4.2).

Запрашивает профиль, подтверждённые факты, историю диалога и релевантные
фрагменты базы знаний, собирая их в ConversationContext в заданном порядке
приоритета. Также определяет (docs/02, §4, §11), зависит ли запрос от
документов базы знаний, — при недоступности сервиса поиска для таких
запросов ответ не подменяется общими знаниями модели.
"""

from __future__ import annotations

from dekoder.modules.ai_core.domain.message import IncomingMessage
from dekoder.modules.memory.application.ports import DialogueHistoryPort, FactRepositoryPort
from dekoder.modules.profile.application.ports import ProfileRepositoryPort
from dekoder.modules.search.application.ports import KnowledgeSearchPort
from dekoder.shared.application.conversation_context import ConversationContext


class BuildConversationContextUseCase:
    """Не вызывает LLM и не решает, что с контекстом делать дальше — только собирает его."""

    def __init__(
        self,
        profile_repository: ProfileRepositoryPort,
        dialogue_history: DialogueHistoryPort,
        fact_repository: FactRepositoryPort,
        knowledge_search: KnowledgeSearchPort,
    ) -> None:
        self._profile_repository = profile_repository
        self._dialogue_history = dialogue_history
        self._fact_repository = fact_repository
        self._knowledge_search = knowledge_search

    def execute(self, message: IncomingMessage) -> ConversationContext:
        raise NotImplementedError
