"""
Минимальные доменные value objects первого вертикального среза — только то,
что нужно для одного сообщения к модели (текст, модель, провайдер). Ноль
зависимостей от Pydantic/FastAPI/Telegram/OpenRouter — чистый Python.

`User`/`Conversation`/`Message` (агрегаты, объединяющие эти value objects
в историю диалога) сюда не входят — следующий спринт.

Ошибки — обычный `ValueError` с понятным сообщением: отдельная доменная
ошибка пока не оправдана (нет ни одного сценария, различающего эти три
случая невалидности между собой на уровне обработки).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class MessageText:
    """Текст одного сообщения (пользователя или модели) — непустой, без краевых пробелов, ограниченной длины."""

    MAX_LENGTH: ClassVar[int] = 4000

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if not stripped:
            raise ValueError("MessageText не может быть пустым")
        if len(stripped) > self.MAX_LENGTH:
            raise ValueError(
                f"MessageText превышает максимальную длину {self.MAX_LENGTH} символов (получено {len(stripped)})"
            )
        object.__setattr__(self, "value", stripped)


@dataclass(frozen=True, slots=True)
class ModelId:
    """Идентификатор модели, использованной в конкретном сообщении (например, `openai/gpt-4o-mini`)."""

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if not stripped:
            raise ValueError("ModelId не может быть пустым")
        object.__setattr__(self, "value", stripped)


@dataclass(frozen=True, slots=True)
class ProviderId:
    """Идентификатор поставщика модели (например, `openrouter`)."""

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if not stripped:
            raise ValueError("ProviderId не может быть пустым")
        object.__setattr__(self, "value", stripped)
