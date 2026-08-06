"""
TelegramBot — единственный driving-канал MVP (docs/versions/02, §5; §14).
Вызывает только application/ai_core/ (docs/versions/03, §7).
"""

from __future__ import annotations

from dekoder.application.ai_core.use_cases.generate_content import GenerateContentUseCase
from dekoder.application.ai_core.use_cases.regenerate import RegenerateUseCase
from dekoder.application.ai_core.use_cases.route_command import RouteCommandUseCase


class TelegramBot:
    def __init__(
        self,
        bot_token: str,
        webhook_secret: str,
        generate_content: GenerateContentUseCase,
        regenerate: RegenerateUseCase,
        route_command: RouteCommandUseCase,
    ) -> None:
        self._bot_token = bot_token
        self._webhook_secret = webhook_secret
        self._generate_content = generate_content
        self._regenerate = regenerate
        self._route_command = route_command

    def start(self) -> None:
        raise NotImplementedError
