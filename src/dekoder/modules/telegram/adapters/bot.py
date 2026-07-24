"""
Telegram driving adapter (docs/02, §5: «не принимает решений о содержании
ответа, не обращается к LLM/Qdrant/SQLite напрямую»).

Конкретная библиотека клиента Telegram Bot API не зафиксирована в
утверждённых документах и не подключается на этом шаге.
"""

from __future__ import annotations

from dekoder.modules.ai_core.application.ports import ConversationPort


class TelegramBot:
    """Точка запуска Telegram-бота: подписывается на обновления и делегирует их handlers."""

    def __init__(self, bot_token: str, webhook_secret: str, conversation: ConversationPort) -> None:
        self._bot_token = bot_token
        self._webhook_secret = webhook_secret
        self._conversation = conversation

    def start(self) -> None:
        raise NotImplementedError
