"""
Координатор AI Core (docs/02, §8, §10).

ProcessUserMessageUseCase реализует ConversationPort и последовательно
вызывает специализированные use case'ы: маршрутизацию команд
(route_conversation_command.py), сборку контекста
(build_conversation_context.py) и генерацию ответа
(generate_assistant_response.py). Сам не содержит правил маршрутизации,
приоритета источников контекста или обращения к LLM — это вынесено в
соответствующие файлы этого пакета (см. docs/03, §16).
"""

from __future__ import annotations

from dekoder.modules.ai_core.application.ports import ConversationPort
from dekoder.modules.ai_core.application.use_cases.build_conversation_context import (
    BuildConversationContextUseCase,
)
from dekoder.modules.ai_core.application.use_cases.generate_assistant_response import (
    GenerateAssistantResponseUseCase,
)
from dekoder.modules.ai_core.application.use_cases.route_conversation_command import (
    RouteConversationCommandUseCase,
)
from dekoder.modules.ai_core.domain.message import IncomingMessage, OutgoingResponse
from dekoder.modules.logging_audit.application.ports import LoggerPort
from dekoder.modules.memory.application.ports import DialogueHistoryPort


class ProcessUserMessageUseCase(ConversationPort):
    """
    Последовательность (docs/02, §8, §10):
    1) сохранить реплику пользователя (record_user_message, статус received);
    2) попытаться обработать как команду памяти (route_command);
    3) если это не команда — собрать контекст (build_context) и получить
       ответ модели (generate_response);
    4) сохранить ответ ассистента отдельной записью и перевести статус
       реплики пользователя в completed, либо в failed при ошибке.
    """

    def __init__(
        self,
        dialogue_history: DialogueHistoryPort,
        route_command: RouteConversationCommandUseCase,
        build_context: BuildConversationContextUseCase,
        generate_response: GenerateAssistantResponseUseCase,
        logger: LoggerPort,
    ) -> None:
        self._dialogue_history = dialogue_history
        self._route_command = route_command
        self._build_context = build_context
        self._generate_response = generate_response
        self._logger = logger

    def handle(self, message: IncomingMessage) -> OutgoingResponse:
        """Реализация появится вместе с подключением конкретных адаптеров."""
        raise NotImplementedError
