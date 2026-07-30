"""
LLMProvider — абстрактный контракт вызова генеративной модели.

`application/conversation/` не импортирует OpenRouter (или любого другого
конкретного провайдера) — только этот протокол. Конкретные реализации
(например, адаптер OpenRouter) живут в `infrastructure/` и подключаются
через composition root, как и остальные порты проекта.

Только `generate()` — `healthcheck()` не добавлен, т.к. сейчас нет
use case'а, который бы его вызывал (см. задачу: не создавать
неиспользуемые методы).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from dekoder.application.conversation.dto import LLMRequest, LLMResponse


@runtime_checkable
class LLMProvider(Protocol):
    """
    `@runtime_checkable` включает `isinstance(obj, LLMProvider)` — только
    проверка наличия метода нужной формы, не сигнатуры типов, но этого
    достаточно, чтобы в тестах утверждать «fake-объект соответствует порту»,
    не наследуясь от него явно.
    """

    async def generate(self, request: LLMRequest) -> LLMResponse: ...
