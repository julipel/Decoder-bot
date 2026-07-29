"""AdminSessionCookies — подпись/проверка сессионной cookie панели администратора (docs/versions/02, §13)."""

from __future__ import annotations


class AdminSessionCookies:
    def __init__(self, session_secret: str) -> None:
        self._session_secret = session_secret

    def create_cookie(self, session_token: str) -> str:
        raise NotImplementedError

    def read_session_token(self, cookie_header: str) -> str | None:
        raise NotImplementedError
