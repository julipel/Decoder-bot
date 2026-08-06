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

С задачи S5-06 (Sprint 5, ADR-5.6/5.11) `ProcessUserMessage` дополнительно
получает `max_relevant_memory=settings.memory.max_relevant_records` —
лимит `MemoryRepository.find_relevant`, вызываемого внутри транзакции 1
(`repositories_factory` уже собирает `SQLAlchemyMemoryRepository` как
поле `ConversationRepositories.memory`, задача S5-03/S5-04 — здесь
ничего дополнительно не собирается, `repositories_factory` переиспользуется
как есть). Ни `PromptBuilder`, ни `TokenBudgetPolicy` этой задачей не
меняются.

С задачи S5-07 контейнер также собирает `CreateMemoryRecordUseCase`/
`ListMemoryRecordsUseCase`/`DeleteMemoryRecordUseCase`
(`application/memory/use_cases/*`) поверх той же `repositories_factory` —
по тем же причинам, что и `ListProfiles`/`GetActiveProfile`/
`SelectProfile` (ни один не требует `LLMProvider`, никакой второй
фабрики репозиториев не вводится, ADR-5.5). `ConfirmMemoryRecordUseCase`/
`RejectMemoryRecordUseCase` НЕ собираются здесь — нет вызывающего
Telegram-сценария в Sprint 5 (ADR-5.9), контейнер не создаёт объекты,
которые некому передать.

С задачи S6-08 (Sprint 6, ADR-6.4) контейнер также собирает
`SemanticSearchService` (`application/knowledge/services/
semantic_search_service.py`) — композицию `OpenAiEmbeddingProvider`
(поверх отдельного `openai_http_client`, независимого от
`http_client`/OpenRouter, ADR-6.3) и `QdrantVectorRepository` (поверх
`qdrant_client`) — и внедряет её в `ProcessUserMessage` как
`knowledge_search`, параллельно `llm_provider`. `IndexKnowledgeDocumentUseCase`/
`DeleteKnowledgeDocumentUseCase` здесь НЕ собираются — индексация не
часть диалогового контейнера (ADR-6.4/ADR-6.6), её собирает отдельно
`scripts/index_document.py` (задача S6-09), не `api`/`telegram-bot`.

С задачи S7-06 (Sprint 7, ADR-7.4/7.7) контейнер также собирает
`ConfigModelCatalogRepository` (`infrastructure/model_catalog/
config_repository.py`, парсит `catalog.json` один раз при построении,
путь — `settings.model_catalog.catalog_path`, не хардкод) и внедряет её
в `ProcessUserMessage` как `model_catalog`, тем же приёмом, что и
`knowledge_search` (отдельный конструкторный параметр, не через
`ConversationRepositoriesFactory` — каталог не пользовательские, не
транзакционные данные, ADR-7.4).

С задачи S7-07 (Sprint 7, ADR-7.9) контейнер также собирает
`ListAvailableModels`/`GetSelectedModel`/`SelectModel`
(`application/model_catalog/use_cases/*`) поверх той же
`repositories_factory` (ни один не требует `LLMProvider`, никакой второй
фабрики репозиториев не вводится, ADR-7.5) и уже собранного
`model_catalog` (та же единственная загруженная копия каталога, что и у
`ProcessUserMessage`) — по тем же причинам, что и `ListProfiles`/
`GetActiveProfile`/`SelectProfile`.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dekoder.application.conversation.use_cases.clear_conversation import ClearConversation
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.application.conversation.use_cases.start_new_conversation import StartNewConversation
from dekoder.application.knowledge.services.semantic_search_service import SemanticSearchService
from dekoder.application.memory.use_cases.create_memory_record import CreateMemoryRecordUseCase
from dekoder.application.memory.use_cases.delete_memory_record import DeleteMemoryRecordUseCase
from dekoder.application.memory.use_cases.list_memory_records import ListMemoryRecordsUseCase
from dekoder.application.model_catalog.use_cases.get_selected_model import GetSelectedModel
from dekoder.application.model_catalog.use_cases.list_models import ListAvailableModels
from dekoder.application.model_catalog.use_cases.select_model import SelectModel
from dekoder.application.profile.use_cases.get_active_profile import GetActiveProfile
from dekoder.application.profile.use_cases.list_profiles import ListProfiles
from dekoder.application.profile.use_cases.select_profile import SelectProfile
from dekoder.application.prompt.services.prompt_builder import DeterministicPromptBuilder
from dekoder.application.prompt.services.token_budget import estimate_size
from dekoder.bootstrap.repositories import build_conversation_repositories_factory
from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.prompt.policies import TokenBudgetPolicy
from dekoder.infrastructure.embeddings.openai_embedding_provider import OpenAiEmbeddingProvider
from dekoder.infrastructure.llm.openrouter_adapter import OpenRouterLLMAdapter
from dekoder.infrastructure.model_catalog.config_repository import ConfigModelCatalogRepository
from dekoder.infrastructure.prompts.file_template_repository import FileTemplateRepository
from dekoder.infrastructure.qdrant.vector_repository import QdrantVectorRepository
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
    create_memory_record: CreateMemoryRecordUseCase
    list_memory_records: ListMemoryRecordsUseCase
    delete_memory_record: DeleteMemoryRecordUseCase
    list_available_models: ListAvailableModels
    get_selected_model: GetSelectedModel
    select_model: SelectModel


def build_container(
    settings: Settings,
    http_client: httpx.AsyncClient,
    openai_http_client: httpx.AsyncClient,
    qdrant_client: AsyncQdrantClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> ApplicationContainer:
    """
    Собирает use cases, внедряя в них конкретный `LLMProvider` поверх уже
    готового `http_client` и конкретную `ConversationRepositoriesFactory`
    (задача S2-06) поверх уже готовой `db_session_factory`
    (`bootstrap/database.py::init_database`). `StartNewConversation`
    (задача S2-08) и `ClearConversation` (задача S2-10) переиспользуют ту
    же `repositories_factory`, что и `ProcessUserMessage` — не отдельную
    фабрику. `openai_http_client`/`qdrant_client` (задача S6-08) — уже
    готовые клиенты для `SemanticSearchService`, тем же приёмом, что и
    `http_client` для `OpenRouterLLMAdapter`: контейнер не отвечает за их
    подключение/закрытие.
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
    embedding_provider = OpenAiEmbeddingProvider(
        client=openai_http_client,
        api_key=settings.openai.api_key.get_secret_value(),
        model=settings.openai.embedding_model,
    )
    vector_repository = QdrantVectorRepository(
        client=qdrant_client,
        collection_name=settings.qdrant.collection_name,
    )
    knowledge_search = SemanticSearchService(
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        limit=settings.knowledge.search_limit,
        min_relevance_score=settings.knowledge.min_relevance_score,
    )
    model_catalog = ConfigModelCatalogRepository(catalog_path=settings.model_catalog.catalog_path)
    process_user_message = ProcessUserMessage(
        llm_provider=llm_provider,
        repositories=repositories_factory,
        prompt_builder=prompt_builder,
        knowledge_search=knowledge_search,
        model_catalog=model_catalog,
        default_model=ModelId(settings.openrouter.default_model),
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
        max_relevant_memory=settings.memory.max_relevant_records,
    )
    start_new_conversation = StartNewConversation(repositories=repositories_factory)
    clear_conversation = ClearConversation(repositories=repositories_factory)
    list_profiles = ListProfiles(repositories=repositories_factory)
    get_active_profile = GetActiveProfile(repositories=repositories_factory)
    select_profile = SelectProfile(repositories=repositories_factory)
    create_memory_record = CreateMemoryRecordUseCase(repositories=repositories_factory)
    list_memory_records = ListMemoryRecordsUseCase(repositories=repositories_factory)
    delete_memory_record = DeleteMemoryRecordUseCase(repositories=repositories_factory)
    list_available_models = ListAvailableModels(repositories=repositories_factory, model_catalog=model_catalog)
    get_selected_model = GetSelectedModel(repositories=repositories_factory, model_catalog=model_catalog)
    select_model = SelectModel(repositories=repositories_factory, model_catalog=model_catalog)
    return ApplicationContainer(
        settings=settings,
        process_user_message=process_user_message,
        start_new_conversation=start_new_conversation,
        clear_conversation=clear_conversation,
        list_profiles=list_profiles,
        get_active_profile=get_active_profile,
        select_profile=select_profile,
        create_memory_record=create_memory_record,
        list_memory_records=list_memory_records,
        delete_memory_record=delete_memory_record,
        list_available_models=list_available_models,
        get_selected_model=get_selected_model,
        select_model=select_model,
    )
