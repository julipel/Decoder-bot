"""
Обращение к активному поставщику языковой модели (docs/01, §4.2).

Преобразует ConversationContext в LLMRequestContext (собственный DTO
модуля llm — см. llm/application/ports.py, docs/03 §9) и вызывает LLMPort.
Не решает, что включать в контекст, — это ответственность
build_conversation_context.py.
"""

from __future__ import annotations

from dekoder.modules.llm.application.ports import LLMPort, LLMResponse
from dekoder.shared.application.conversation_context import ConversationContext


class GenerateAssistantResponseUseCase:
    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    def execute(self, context: ConversationContext) -> LLMResponse:
        raise NotImplementedError
