"""
Маршрутизация команд /запомнить, /память, /забыть (docs/01, §3).

Если сообщение — распознанная команда управления памятью (включая
подтверждение черновика факта), use case делегирует её use case'ам модуля
memory и возвращает готовый ответ. Если сообщение не является командой,
возвращает None — тогда координатор (process_user_message.py) переходит к
обычному конвейеру «контекст → LLM» (см. build_conversation_context.py).
"""

from __future__ import annotations

from dekoder.modules.ai_core.domain.message import IncomingMessage, OutgoingResponse
from dekoder.modules.memory.application.use_cases.manage_facts import (
    ConfirmFactUseCase,
    ForgetFactUseCase,
    ListFactsUseCase,
    StageFactUseCase,
)


class RouteConversationCommandUseCase:
    """Не знает про профиль, историю, поиск или LLM — только про команды памяти."""

    def __init__(
        self,
        stage_fact: StageFactUseCase,
        confirm_fact: ConfirmFactUseCase,
        list_facts: ListFactsUseCase,
        forget_fact: ForgetFactUseCase,
    ) -> None:
        self._stage_fact = stage_fact
        self._confirm_fact = confirm_fact
        self._list_facts = list_facts
        self._forget_fact = forget_fact

    def route(self, message: IncomingMessage) -> OutgoingResponse | None:
        """Возвращает готовый ответ для команды либо None, если это обычное сообщение."""
        raise NotImplementedError
