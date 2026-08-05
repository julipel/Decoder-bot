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

С задачи S3-06 (Sprint 3) контейнер также собирает `ListProfiles`/
`GetActiveProfile`/`SelectProfile` (`application/profile/use_cases/*`)
поверх той же `repositories_factory` — по тем же причинам, что и
`StartNewConversation`/`ClearConversation` (ни один из трёх не требует
`LLMProvider`); никакой второй фабрики репозиториев не вводится (ADR-3.3).

С задачи S4-07 (Sprint 4, ADR-4.1/4.2/4.7) контейнер также собирает
Prompt Engine — `FileTemplateRepository` (`infrastructure/prompts/
file_template_repository.py`, читает сид-шаблоны один раз при построении,
ADR-4.2) и `DeterministicPromptBuilder` (`application/prompt/services/
prompt_builder.py`), внедряемый в `ProcessUserMessage` вместо прежней
константы `_DEFAULT_SYSTEM_PROMPT`/параметра `default_system_prompt`
(Sprint 2/3) — базовая системная инструкция теперь безусловная секция 1
Prompt Engine (текст мигрировал в `infrastructure/prompts/templates/
base_instruction.txt`, задача S4-04), а не Python-константа этого модуля.
`TokenBudgetPolicy` (`domain/prompt/policies.py`) конфигурируется
эвристикой символов (`application/prompt/services/token_budget.py::
estimate_size`, ADR-4.4) и бюджетом из `Settings.prompt.token_budget`
(не хардкод) — `PromptTemplateRepository` не встраивается в
`ConversationRepositoriesFactory`, внедряется в `DeterministicPromptBuilder`
напрямую (ADR-4.2/4.3, нет второй фабрики репозиториев).

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
from dekoder.application.profile.use_cases.get_active_profile import GetActiveProfile
from dekoder.application.profile.use_cases.list_profiles import ListProfiles
from dekoder.application.profile.use_cases.select_profile import SelectProfile
from dekoder.application.prompt.services.prompt_builder import DeterministicPromptBuilder
from dekoder.application.prompt.services.token_budget import estimate_size
from dekoder.bootstrap.repositories import build_conversation_repositories_factory
from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.prompt.policies import TokenBudgetPolicy
from dekoder.infrastructure.llm.openrouter_adapter import OpenRouterLLMAdapter
from dekoder.infrastructure.prompts.file_template_repository import FileTemplateRepository
from dekoder.shared.config import Settings


@dataclass(frozen=True)
class ApplicationContainer:
    settings: Settings
    process_user_message: ProcessUserMessage
    start_new_conversation: StartNewConversation
    clear_conversation: ClearConversation
    list_profiles: ListProfiles
    get_active_profile: GetActiveProfile
    select_profile: SelectProfile


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
    prompt_template_repository = FileTemplateRepository()
    token_budget_policy = TokenBudgetPolicy(estimate_size=estimate_size)
    prompt_builder = DeterministicPromptBuilder(
        template_repository=prompt_template_repository,
        token_budget_policy=token_budget_policy,
        budget=settings.prompt.token_budget,
    )
    process_user_message = ProcessUserMessage(
        llm_provider=llm_provider,
        repositories=repositories_factory,
        prompt_builder=prompt_builder,
        default_model=ModelId(settings.openrouter.default_model),
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
    )
    start_new_conversation = StartNewConversation(repositories=repositories_factory)
    clear_conversation = ClearConversation(repositories=repositories_factory)
    list_profiles = ListProfiles(repositories=repositories_factory)
    get_active_profile = GetActiveProfile(repositories=repositories_factory)
    select_profile = SelectProfile(repositories=repositories_factory)
    return ApplicationContainer(
        settings=settings,
        process_user_message=process_user_message,
        start_new_conversation=start_new_conversation,
        clear_conversation=clear_conversation,
        list_profiles=list_profiles,
        get_active_profile=get_active_profile,
        select_profile=select_profile,
    )
