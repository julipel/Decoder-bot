"""Единый профиль автора (docs/01, §2.3): один общий профиль на всех пользователей."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Profile:
    """Стиль изложения и ограничения, которые AI Core применяет к форме ответа."""

    style: str
    constraints: tuple[str, ...] = field(default_factory=tuple)
