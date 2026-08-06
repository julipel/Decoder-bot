"""
TelegramUpdateHandler — переводит обновления Telegram Bot API в вызовы
application/ai_core/ и обратно (docs/versions/02, §5). Реальные типы
python-telegram-bot: FastAPI/PTB уже реальные зависимости (docs/versions/06, §5).
"""

from __future__ import annotations

import telegram

from dekoder.application.ai_core.use_cases.generate_content import GenerateContentUseCase
from dekoder.application.ai_core.use_cases.regenerate import RegenerateUseCase
from dekoder.application.ai_core.use_cases.route_command import RouteCommandUseCase


class TelegramUpdateHandler:
    def __init__(
        self,
        generate_content: GenerateContentUseCase,
        regenerate: RegenerateUseCase,
        route_command: RouteCommandUseCase,
    ) -> None:
        self._generate_content = generate_content
        self._regenerate = regenerate
        self._route_command = route_command

    async def handle_update(self, update: telegram.Update) -> None:
        raise NotImplementedError

    async def _send_response(self, chat_id: int, text: str) -> None:
        raise NotImplementedError
