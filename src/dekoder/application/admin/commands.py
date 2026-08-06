"""Команды Admin (docs/versions/05, §4) — единственный кросс-модульный оркестратор наравне с ai_core."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticateAdminCommand:
    login: str
    password: str
