"""Тесты presentation/telegram/bot.py::build_telegram_application — без обращения к реальному Telegram API."""

from __future__ import annotations

from dekoder.presentation.telegram.bot import build_telegram_application

_TEST_BOT_TOKEN = "123456:test-token"  # noqa: S105 - фиктивный токен для теста, не секрет


class TestBuildTelegramApplication:
    def test_no_proxy_by_default(self) -> None:
        application = build_telegram_application(bot_token=_TEST_BOT_TOKEN)

        request = application.bot.request
        assert request._client_kwargs["proxy"] is None

    def test_proxy_url_reaches_the_httpx_client(self) -> None:
        application = build_telegram_application(bot_token=_TEST_BOT_TOKEN, proxy_url="socks5://example.com:1080")

        request = application.bot.request
        assert request._client_kwargs["proxy"] == "socks5://example.com:1080"
