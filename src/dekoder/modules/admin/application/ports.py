"""AdminAuthPort (docs/02, §7 — владелец: административный application-модуль, а не веб-панель)."""

from __future__ import annotations

from typing import Protocol


class AdminAuthPort(Protocol):
    """Аутентификация единственной административной учётной записи (docs/01, §4.7)."""

    def authenticate(self, login: str, password: str) -> str:
        """Сравнивает пароль с хешем из переменной окружения, возвращает токен сессии."""
        ...

    def validate_session(self, session_token: str) -> bool: ...
