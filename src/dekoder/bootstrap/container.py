"""
ApplicationContainer — контейнер зависимостей вертикального среза, без
внешней DI-библиотеки: обычный неизменяемый `dataclass` с уже собранными
объектами.

Это не service locator: контейнер ничего не ищет по строковому имени и
не хранится в глобальной переменной, доступной любому модулю на
импорте, — получить его можно только там, куда он явно передан
(`app.state` в `bootstrap/application.py`, либо напрямую в тестах).

`build_container()` — единственное место, которому разрешено знать
одновременно про `Settings`, конкретный `LLMProvider`
(`OpenRouterLLMAdapter`) и (с задачи S2-06) конкретную фабрику
репозиториев (`bootstrap/repositories.py::
build_conversation_repositories_factory`). Ни Telegram-слой, ни любой
другой driving-адаптер не импортирует адаптер или репозитории напрямую —
только уже собранный `ApplicationContainer.process_user_message` (и, с
задачи S2-08, `ApplicationContainer.start_new_conversation`).

С задачи S2-08 контейнер также собирает `StartNewConversation`
(`application/conversation/use_cases/start_new_conversation.py`) поверх
той же самой `repositories_factory`, что уже используется
`ProcessUserMessage` — не отдельная, вторая фабрика (`StartNewConversation`
не требует `LLMProvider`, поэтому опирается только на репозитории).

С задачи S2-10 контейнер также собирает `ClearConversation`
(`application/conversation/use_cases/clear_conversation.py`) поверх той же
`repositories_factory` — по тем же причинам, что и `StartNewConversation`
(`ClearConversation` тоже не требует `LLMProvider`).

`http_client` контейнер получает уже созданным и не отвечает за его
жизненный цикл — открывает и закрывает клиент `bootstrap/application.py`
через FastAPI lifespan. Аналогично с задачи S2-06 — `db_session_factory`
(единая фабрика сессий, `bootstrap/database.py::init_database`) контейнер
тоже получает уже созданной, не создаёт её сам.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dekoder.application.conversation.use_cases.clear_conversation import ClearConversation
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.application.conversation.use_cases.start_new_conversation import StartNewConversation
from dekoder.bootstrap.repositories import build_conversation_repositories_factory
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
    start_new_conversation: StartNewConversation
    clear_conversation: ClearConversation


def build_container(
    settings: Settings,
    http_client: httpx.AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> ApplicationContainer:
    """
    Собирает use cases, внедряя в них конкретный `LLMProvider` поверх уже
    готового `http_client` и конкретную `ConversationRepositoriesFactory`
    (задача S2-06) поверх уже готовой `db_session_factory`
    (`bootstrap/database.py::init_database`). `StartNewConversation`
    (задача S2-08) и `ClearConversation` (задача S2-10) переиспользуют ту
    же `repositories_factory`, что и `ProcessUserMessage` — не отдельную
    фабрику.
    """
    llm_provider = OpenRouterLLMAdapter(
        client=http_client,
        api_key=settings.openrouter.api_key.get_secret_value(),
        x_title=settings.application.name,
    )
    repositories_factory = build_conversation_repositories_factory(db_session_factory)
    process_user_message = ProcessUserMessage(
        llm_provider=llm_provider,
        repositories=repositories_factory,
        default_model=ModelId(settings.openrouter.default_model),
        system_prompt=_DEFAULT_SYSTEM_PROMPT,
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
    )
    start_new_conversation = StartNewConversation(repositories=repositories_factory)
    clear_conversation = ClearConversation(repositories=repositories_factory)
    return ApplicationContainer(
        settings=settings,
        process_user_message=process_user_message,
        start_new_conversation=start_new_conversation,
        clear_conversation=clear_conversation,
    )
