"""
Точка входа второго процесса — Telegram polling (`python -m
dekoder.telegram_main`), запускается отдельным контейнером
(`telegram-bot`) из того же образа, что и ASGI-процесс `main.py`.

Тонкая обёртка над bootstrap-слоем, как и `main.py`: не содержит
конфигурации и не знает деталей сборки контейнера зависимостей —
`Settings()` создаётся один раз, здесь же.

`Application.run_polling()` (python-telegram-bot) сам управляет своим
event loop'ом и уже устанавливает обработчики SIGINT/SIGTERM/SIGABRT
для корректной остановки polling — то, что нужно `docker compose stop`/
`down` (требование «проверь корректное завершение Telegram polling»).
"""

from __future__ import annotations

import httpx
from telegram.ext import Application

from dekoder.bootstrap.container import build_container
from dekoder.presentation.telegram.bot import build_telegram_application
from dekoder.shared.config import Settings
from dekoder.shared.logging import configure_logging, get_logger

_logger = get_logger(__name__)


def main() -> None:
    settings = Settings()
    configure_logging(
        environment=settings.application.environment,
        level="DEBUG" if settings.application.debug else "INFO",
    )

    http_client = httpx.AsyncClient(
        base_url=settings.openrouter.base_url,
        timeout=settings.llm.timeout,
    )
    container = build_container(settings, http_client)
    application = build_telegram_application(
        bot_token=settings.telegram.bot_token.get_secret_value(),
        process_user_message=container.process_user_message,
    )

    async def _log_started(_: Application) -> None:
        # post_init вызывается после успешной Application.initialize()
        # (в т.ч. getMe) — если этот лог не появился, polling не начался.
        _logger.info("telegram_polling_started")

    async def _close_http_client(_: Application) -> None:
        # Вызывается run_polling() при штатной остановке (после
        # обработки SIGINT/SIGTERM) — здесь http_client реально закрывается.
        _logger.info("telegram_polling_stopping")
        await http_client.aclose()

    application.post_init = _log_started
    application.post_shutdown = _close_http_client
    application.run_polling()


if __name__ == "__main__":
    main()
