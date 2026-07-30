"""
ApplicationContainer — контейнер зависимостей первого вертикального
среза, без внешней DI-библиотеки: обычный неизменяемый `dataclass` с уже
собранными объектами.

Это не service locator: контейнер ничего не ищет по строковому имени и
не хранится в глобальной переменной, доступной любому модулю на
импорте, — получить его можно только там, куда он явно передан
(`app.state` в `bootstrap/application.py`, либо напрямую в тестах).

`build_container()` — единственное место, которому разрешено знать
одновременно про `Settings` и конкретный `LLMProvider`
(`OpenRouterLLMAdapter`). Ни Telegram-слой, ни любой другой driving-
адаптер не импортирует адаптер напрямую — только уже собранный
`ApplicationContainer.process_user_message`.

`http_client` контейнер получает уже созданным и не отвечает за его
жизненный цикл — открывает и закрывает клиент `bootstrap/application.py`
через FastAPI lifespan.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.domain.conversation.value_objects import ModelId
from dekoder.infrastructure.llm.openrouter_adapter import OpenRouterLLMAdapter
from dekoder.shared.config import Settings

# Временный минимальный системный промпт — до отдельного этапа Prompt
# Engine (вне объёма текущей задачи, как и в задаче ProcessUserMessage).
_DEFAULT_SYSTEM_PROMPT = "Ты — персональный ассистент «Декодер». Отвечай кратко и по делу."


@dataclass(frozen=True)
class ApplicationContainer:
    settings: Settings
    process_user_message: ProcessUserMessage


def build_container(settings: Settings, http_client: httpx.AsyncClient) -> ApplicationContainer:
    """Собирает use case, внедряя в него конкретный LLMProvider поверх уже готового http_client."""
    llm_provider = OpenRouterLLMAdapter(
        client=http_client,
        api_key=settings.openrouter.api_key.get_secret_value(),
        x_title=settings.application.name,
    )
    process_user_message = ProcessUserMessage(
        llm_provider=llm_provider,
        default_model=ModelId(settings.openrouter.default_model),
        system_prompt=_DEFAULT_SYSTEM_PROMPT,
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
    )
    return ApplicationContainer(settings=settings, process_user_message=process_user_message)
