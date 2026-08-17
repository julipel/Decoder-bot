"""
ProcessUserMessage — центральный use case обработки одного входящего
пользовательского сообщения (Telegram → ProcessUserMessage → LLMProvider →
OpenRouter → ответ), эволюционировавший в Sprint 2 (задача S2-06) —
теперь идентифицирует пользователя, получает/создаёт активный диалог,
сохраняет сообщения и формирует LLM-контекст из истории, а не работает
stateless одним сообщением, как в Sprint 1; в Sprint 3 (задача S3-07,
ADR-3.3) — системная инструкция берётся из активного профиля вызывающего
пользователя вместо статической глобальной константы; и в Sprint 4
(задача S4-07, ADR-4.1/4.7/4.8) — построение промпта (и системной
инструкции, и списка сообщений истории) целиком переезжает в
`PromptBuilder` (Prompt Engine) — этот use case больше не строит
`LLMMessage`/строку системного промпта самостоятельно.

Зависит только от портов (`LLMProvider`, `ConversationRepositoriesFactory`,
`PromptBuilder`), DTO собственного модуля и доменных типов (`Message`,
`MessageRole`, `MessageText`, `ModelId`, `PromptContext`) — ни httpx, ни
SQLAlchemy, ни ORM-моделей, ни Telegram, ни FastAPI, ни URL конкретного
провайдера, ни переменных окружения. Настройки (`default_model`/
`temperature`/`max_tokens`) приходят через конструктор — это
ответственность bootstrap-слоя, как и раньше. Константа
`_DEFAULT_SYSTEM_PROMPT`/параметр `default_system_prompt` (Sprint 2/3)
удалены (S4-07) — базовая инструкция, ранее подставлявшаяся как fallback
на пустой профиль, теперь безусловная секция 1 Prompt Engine (ADR-4.7),
рендерящаяся `PromptBuilder` независимо от содержимого профиля.

Prompt Engine (Sprint 4, задача S4-07, ADR-4.1/4.7/4.8): `_save_user_message`
(транзакция 1) сразу после получения/создания `User`/`Conversation`
читает `repositories.profiles.get_active_profile(user.id)` — тем же
вызовом `self._repositories()`, без отдельной транзакции — и возвращает
`(conversation_id, profile: UserProfile)` вместо прежнего
`(conversation_id, system_instruction: str)` (ADR-4.8): извлечение и
дефолтинг строки инструкции больше не ответственность этого use case —
`execute()` собирает `PromptContext(profile=profile, dialogue_history=history)`
из уже полученных транзакциями данных и передаёт его
`self._prompt_builder.build(context)` (синхронный, без I/O — ADR-4.1/4.8),
получая обратно `PromptBuildResult` с готовыми `system_prompt`/`messages`/
`template_versions`; `LLMRequest` строится из результата практически без
преобразований («тривиальный транслятор», ADR-4.1) — role-mapping и
склейка секций промпта больше не происходят здесь.

Долговременная память (Sprint 5, задача S5-06, ADR-5.4/5.6/5.11): тем же
приёмом, что и `profile` — сразу после `repositories.profiles.
get_active_profile(user.id)`, ещё внутри транзакции 1, `_save_user_message`
читает `repositories.memory.find_relevant(user.id, limit=self.
_max_relevant_memory)` и возвращает `(conversation_id, profile,
memory_records)`. Отдельного use-case класса `FindRelevantMemory` нет
(ADR-5.4) — порт вызывается напрямую. `execute()` передаёт
`[r.text for r in memory_records]` в `PromptContext.confirmed_memory_facts`
без переупорядочивания (`find_relevant` уже вернул `confidence DESC,
created_at DESC`, ADR-5.6/5.11) — ни один файл `domain/prompt/`/
`application/prompt/`/`infrastructure/prompts/` этой задачей не меняется,
секция 4 промпта (Sprint 4) рендерит переданные факты без единого
изменения на своей стороне.

Транзакционные границы (backlog_2.md §9, «Транзакционные границы»,
не изменены в Sprint 4, ADR-4.8):

    Транзакция 1 (`_save_user_message`):
        get/create User -> get/create Conversation -> save user Message ->
        read active profile -> commit

    Вне транзакции:
        load history (отдельная короткая read-only транзакция,
        `_load_history`) -> PromptBuilder.build() (синхронно, без I/O) ->
        call LLM (полностью вне какой-либо открытой DB-транзакции/сессии)

    Транзакция 2 (`_save_assistant_message`):
        save assistant Message -> commit

Каждая из трёх коротких транзакций — отдельный вызов `self._repositories()`
(`ConversationRepositoriesFactory`, `application/conversation/ports.py`) —
отдельная, независимая `AsyncSession` под капотом (bootstrap-реализация:
`session_scope()`, задача S2-01). Ни одна из них не остаётся открытой во
время сетевого вызова `LLMProvider.generate()` — критическое требование
задачи S2-06, не затронутое интеграцией Prompt Engine (`PromptBuilder.
build()` — синхронная чистая функция, вызывается между двумя короткими
транзакциями, не удерживает ни одну из них открытой).

База знаний / RAG (Sprint 6, задача S6-08, ADR-6.4/6.5): в отличие от
`profile`/`memory` (чтение внутри транзакции 1, чистый SQL), поиск по
базе знаний требует внешних HTTP-вызовов (эмбеддинг запроса + Qdrant) —
он не может жить внутри короткой DB-транзакции наравне с `profiles`/
`memory`. `_knowledge_search: KnowledgeSearchService` внедряется отдельным
параметром конструктора, как `llm_provider` (не через
`ConversationRepositoriesFactory`), и вызывается вне какой-либо
DB-транзакции — сразу после `_load_history`, перед сборкой
`PromptContext` — тем же местом в потоке выполнения, где раньше (до
Sprint 6) сразу следовал вызов `PromptBuilder.build()`. Найденные
`SearchResult` форматируются в строки с указанием источника
(`_format_knowledge_fragment`) и передаются в
`PromptContext.knowledge_fragments`; ни один файл `domain/prompt/`/
`application/prompt/`/`infrastructure/prompts/` этой задачей не меняется
(ADR-6.5, тот же приём, что и ADR-5.11 для памяти) — из шаблона знаний
меняется только статический текст (защита от prompt injection, §14.9),
не код. Сбой поиска (эмбеддинги/Qdrant недоступны) не должен обрушивать
ответ пользователю целиком — в отличие от `LLMProvider.generate()`
(центральная ценность ответа), RAG — дополнение к нему: `_search_knowledge`
перехватывает любую ошибку, логирует и возвращает пустой список,
`PromptContext.knowledge_fragments` в этом случае пуст, как и при
отсутствии релевантных результатов (§14.8: «ответ формируется без RAG»).

Выбор AI-модели (Sprint 7, задача S7-06, ADR-7.7): `_save_user_message`
(транзакция 1) дополнительно разрешает активную модель по приоритету
`command.model_id` (явный override, шаг 1) → `repositories.model_selection.
get_selected(user.id)` (персональный выбор, шаг 2, тем же вызовом
`self._repositories()`, что и `profiles`/`memory`) → `self._default_model`
(умолчание, шаг 3). Для кандидатов шагов 2/3 (не для явного override)
проверяется доступность через `self._model_catalog.get(...)`
(`ModelCatalogRepository`, внедрён отдельным конструкторным параметром —
как `knowledge_search`, не через `ConversationRepositoriesFactory`,
ADR-7.4: каталог — не пользовательские, не транзакционные данные) —
`None`/`ModelAvailability.UNAVAILABLE` приводят к тихому логируемому
откату на `self._default_model` (`logger.warning`, поля
`requested_model_id`/`fallback_model_id`/`user_id`). `GenerationSettings`
разрешённой модели (если найдена в каталоге) используется для
`temperature`/`max_tokens` при построении `LLMRequest` вместо
`self._temperature`/`self._max_tokens`; если модель не найдена в каталоге
(например, использован `self._default_model`, отсутствующий в каталоге
отдельной записью) — используются прежние `self._temperature`/
`self._max_tokens`. `ValidateModelAvailability` из §15.4 не выделяется в
отдельный use-case класс — проверка инкапсулирована в `_resolve_model_id`
ниже (ADR-7.7). Ни один файл `domain/prompt/`/`application/prompt/`/
`infrastructure/prompts/` этой задачей не меняется (ADR-7.8) —
`PromptContext`/`PromptBuildResult` не содержат и не получают поля,
связанного с моделью; `model_id` прикрепляется к `LLMRequest` напрямую,
независимо от сборки промпта, как и раньше (docstring ADR-7.8).

Команды `/new`/`/clear` не входят — отдельные use case
(`StartNewConversation`/`ClearConversation`).

Задача S2-11 (финальная интеграция): `_build_message` гарантирует строго
возрастающий `created_at` в рамках одного экземпляра (`_last_message_created_at`
в `__init__`) — на части сред (в т.ч. эта Windows-машина, подтверждено
вручную) две последовательные `datetime.now(UTC)` внутри одного `execute()`
могут совпасть, а вторичный ключ сортировки `history()` — случайный UUID
(S2-05), не связанный с порядком создания. Без этой гарантии порядок
`user`/`assistant` в истории и, соответственно, в запросе к LLM становится
непредсказуемым при совпадении `created_at`.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from dekoder.application.conversation.dto import (
    LLMRequest,
    ProcessUserMessageCommand,
    ProcessUserMessageResult,
    TokenUsage,
)
from dekoder.application.conversation.ports import (
    ConversationRepositories,
    ConversationRepositoriesFactory,
    LLMProvider,
)
from dekoder.application.knowledge.ports import KnowledgeSearchService
from dekoder.application.model_catalog.ports import ModelCatalogRepository
from dekoder.application.prompt.ports import PromptBuilder
from dekoder.domain.conversation.entities import Message, MessageRole
from dekoder.domain.conversation.value_objects import MessageText, ModelId
from dekoder.domain.knowledge.search import SearchResult
from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.model_catalog.enums import ModelAvailability
from dekoder.domain.profile.entities import UserProfile
from dekoder.domain.prompt.value_objects import PromptContext
from dekoder.shared.errors import ValidationError
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)


class ProcessUserMessage:
    def __init__(
        self,
        llm_provider: LLMProvider,
        repositories: ConversationRepositoriesFactory,
        prompt_builder: PromptBuilder,
        knowledge_search: KnowledgeSearchService,
        model_catalog: ModelCatalogRepository,
        default_model: ModelId,
        temperature: float,
        max_tokens: int,
        max_relevant_memory: int,
    ) -> None:
        self._llm_provider = llm_provider
        self._repositories = repositories
        self._prompt_builder = prompt_builder
        self._knowledge_search = knowledge_search
        self._model_catalog = model_catalog
        self._default_model = default_model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_relevant_memory = max_relevant_memory
        # Найдено при задаче S2-11 (финальная интеграция): системные часы
        # некоторых сред (в т.ч. Windows) недостаточно точны, чтобы две
        # последовательные `datetime.now(UTC)` внутри одного `execute()`
        # (user message -> LLM -> assistant message) гарантированно
        # различались. `MessageRepository.history()` сортирует по
        # `created_at ASC, id ASC` (S2-05) — вторичный ключ `id` (случайный
        # UUID) не связан с порядком создания, поэтому при совпадении
        # `created_at` порядок user/assistant в истории становится
        # непредсказуемым (подтверждено воспроизводимо падающим e2e-тестом,
        # `tests/e2e/test_conversation_persistence_scenario.py`). Это же
        # единственный компонент, обрабатывающий сообщения ВСЕХ
        # пользователей за время жизни процесса (`ProcessUserMessage` —
        # singleton, собирается один раз в `bootstrap/container.py`), поэтому
        # достаточно гарантировать строго возрастающие `created_at` в рамках
        # одного экземпляра — не требует изменений ORM/схемы/репозиториев.
        self._last_message_created_at: datetime | None = None

    async def execute(self, command: ProcessUserMessageCommand) -> ProcessUserMessageResult:
        message_text = self._validate_message_text(command.message_text)

        conversation_id, profile, memory_records, model_id = await self._save_user_message(
            command.telegram_user_id, message_text, command.model_id
        )
        history = await self._load_history(conversation_id)
        knowledge_results = await self._search_knowledge(message_text.value)

        context = PromptContext(
            profile=profile,
            dialogue_history=history,
            confirmed_memory_facts=[record.text for record in memory_records],
            knowledge_fragments=[_format_knowledge_fragment(result) for result in knowledge_results],
        )
        build_result = self._prompt_builder.build(context)

        temperature, max_tokens = self._resolve_generation_settings(model_id)
        request = LLMRequest(
            system_prompt=build_result.system_prompt,
            messages=build_result.messages,
            model_id=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            correlation_id=command.correlation_id,
        )
        response = await self._llm_provider.generate(request)

        assistant_message = await self._save_assistant_message(conversation_id, response.text)

        return ProcessUserMessageResult(
            response_text=response.text,
            provider_id=response.provider_id,
            model_id=response.model_id,
            duration_ms=response.duration_ms,
            conversation_id=conversation_id,
            message_id=assistant_message.id,
            usage=TokenUsage(input_tokens=response.input_tokens, output_tokens=response.output_tokens),
            prompt_template_versions=build_result.template_versions,
        )

    async def _save_user_message(
        self, telegram_user_id: int, message_text: MessageText, override_model_id: ModelId | None
    ) -> tuple[UUID, UserProfile, Sequence[MemoryRecord], ModelId]:
        """
        Транзакция 1 (backlog_2.md §9): получить/создать пользователя,
        получить/создать его активный диалог, прочитать его активный
        профиль (Sprint 3, задача S3-07, ADR-3.3 — тем же вызовом
        `self._repositories()`, не отдельной транзакцией), прочитать
        релевантную память (Sprint 5, задача S5-06, ADR-5.4/5.6 — тем же
        приёмом, сразу после чтения профиля), разрешить активную модель
        (Sprint 7, задача S7-06, ADR-7.7 — тем же приёмом, сразу после
        чтения памяти), сохранить сообщение пользователя — всё поверх
        ОДНОЙ короткоживущей транзакции, завершаемой commit'ом при выходе
        из `async with` (или rollback'ом при любой ошибке, включая ошибку
        сохранения сообщения — LLM в этом случае не вызывается, см.
        докстринг модуля).

        Возвращает `(conversation_id, profile, memory_records, model_id)`
        (Sprint 4, задача S4-07, ADR-4.8; Sprint 5, задача S5-06, ADR-5.6;
        Sprint 7, задача S7-06, ADR-7.7) — раньше (Sprint 2/3) возвращался
        уже вычисленный `system_instruction: str` с fallback-логикой
        внутри этого use case; теперь этот use case передаёт весь
        `UserProfile` и уже отфильтрованные/отсортированные `MemoryRecord`
        (`MemoryRepository.find_relevant`, единственная точка бизнес-
        правила «неподтверждённая память не входит в контекст», ADR-5.6)
        как есть — построение системной инструкции и рендер секции 4
        промпта — ответственность `PromptBuilder`, не здесь; `model_id`
        уже полностью разрешён (приоритет + откат при недоступности,
        ADR-7.7) — `execute()` использует его как есть.
        """
        async with self._repositories() as repositories:
            user = await repositories.users.get_or_create_by_telegram_user_id(telegram_user_id)
            conversation = await repositories.conversations.get_or_create_active(user.id)
            profile = await repositories.profiles.get_active_profile(user.id)
            memory_records = await repositories.memory.find_relevant(user.id, limit=self._max_relevant_memory)
            model_id = await self._resolve_model_id(repositories, user.id, override_model_id)
            user_message = self._build_message(conversation.id, MessageRole.USER, message_text.value)
            await repositories.messages.save(user_message)
            return conversation.id, profile, memory_records, model_id

    async def _resolve_model_id(
        self, repositories: ConversationRepositories, user_id: UUID, override_model_id: ModelId | None
    ) -> ModelId:
        """
        Разрешает активную модель по приоритету (ADR-7.7): явный
        `override_model_id` (шаг 1, если задан — используется как есть,
        без проверки через каталог: override предполагает осознанный
        вызывающий код, не пользовательский ввод) → персональный выбор
        пользователя (шаг 2, `repositories.model_selection.get_selected`,
        тем же приёмом, что `repositories.profiles.get_active_profile`) →
        `self._default_model` (шаг 3). Кандидат шагов 2/3 проверяется
        через `self._model_catalog.get(...)` — `None`/`UNAVAILABLE`
        приводят к тихому логируемому откату на `self._default_model`, без
        диалога с пользователем (заранее заданная политика §15.5).

        Не выделено в отдельный use-case класс `ValidateModelAvailability`
        (§15.4) — вся проверка инкапсулирована здесь, тем же приёмом, что
        и остальные точечные проверки этого use case (ADR-7.7).
        """
        if override_model_id is not None:
            return override_model_id

        selected_model_id = await repositories.model_selection.get_selected(user_id)
        candidate_model_id = selected_model_id if selected_model_id is not None else self._default_model

        catalog_model = self._model_catalog.get(candidate_model_id)
        if catalog_model is None or catalog_model.availability is ModelAvailability.UNAVAILABLE:
            _logger.warning(
                "model_selection_fallback",
                requested_model_id=candidate_model_id.value,
                fallback_model_id=self._default_model.value,
                user_id=str(user_id),
            )
            return self._default_model

        return candidate_model_id

    def _resolve_generation_settings(self, model_id: ModelId) -> tuple[float, int]:
        """
        `GenerationSettings` разрешённой модели, если она найдена в
        каталоге (ADR-7.7/ADR-7.3) — иначе прежние `Settings.llm.
        temperature`/`Settings.llm.max_tokens` (например, `self.
        _default_model` может не иметь отдельной записи в каталоге).
        Применяется к ЛЮБОМУ уже разрешённому `model_id` (после отката
        при недоступности, если он случился) — не только к персональному
        выбору.
        """
        catalog_model = self._model_catalog.get(model_id)
        if catalog_model is None:
            return self._temperature, self._max_tokens
        settings = catalog_model.default_generation_settings
        return settings.temperature, settings.max_tokens

    async def _load_history(self, conversation_id: UUID) -> list[Message]:
        """
        Отдельная короткая read-only транзакция — вне транзакции
        сохранения пользовательского сообщения и вне вызова LLM
        (backlog_2.md §9: «Вне транзакции: load history, call LLM»).
        История уже содержит только что сохранённое сообщение
        пользователя (оно сохранено и закоммичено в `_save_user_message`
        раньше) — добавлять его в контекст повторно не нужно и нельзя.
        """
        async with self._repositories() as repositories:
            return await repositories.messages.history(conversation_id)

    async def _search_knowledge(self, query_text: str) -> Sequence[SearchResult]:
        """
        Вне DB-транзакций (ADR-6.4, см. докстринг модуля). Любая ошибка
        (эмбеддинги/Qdrant недоступны) не должна обрушивать ответ
        пользователю — логируется и трактуется как отсутствие
        релевантного контекста (§14.8: «ответ формируется без RAG»),
        не как сбой всего `execute()`.
        """
        started_at = time.monotonic()
        try:
            results = await self._knowledge_search.search(query_text)
        except Exception as error:
            _logger.error("knowledge_search_failed", error=str(error))
            return []
        _logger.info(
            "knowledge_search_completed",
            chunks_found=len(results),
            duration_ms=round((time.monotonic() - started_at) * 1000, 1),
        )
        return results

    async def _save_assistant_message(self, conversation_id: UUID, response_text: str) -> Message:
        """
        Транзакция 2 (backlog_2.md §9): сохранить ответ ассистента,
        commit при выходе из `async with`. Вызывается только после
        успешного ответа LLM — если сохранение здесь падает, пользователь
        уже сохранён (транзакция 1), LLM повторно не вызывается, а
        ошибка пробрасывается вызывающему коду (см. докстринг модуля).
        """
        assistant_message = self._build_message(conversation_id, MessageRole.ASSISTANT, response_text)
        async with self._repositories() as repositories:
            return await repositories.messages.save(assistant_message)

    def _build_message(self, conversation_id: UUID, role: MessageRole, content: str) -> Message:
        """
        UUID — тем же способом, что и репозитории S2-03/S2-04 (`uuid4()`).

        `created_at` — `datetime.now(UTC)`, но не ниже `created_at`
        предыдущего сообщения, построенного этим же экземпляром (см.
        `_last_message_created_at` в `__init__` — устраняет неустойчивый
        порядок `history()` при недостаточном разрешении системных часов,
        задача S2-11).
        """
        created_at = datetime.now(UTC)
        if self._last_message_created_at is not None and created_at <= self._last_message_created_at:
            created_at = self._last_message_created_at + timedelta(microseconds=1)
        self._last_message_created_at = created_at
        return Message(
            id=uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=created_at,
        )

    @staticmethod
    def _validate_message_text(raw_text: str) -> MessageText:
        try:
            return MessageText(raw_text)
        except ValueError as error:
            raise ValidationError(
                message=f"Некорректный текст пользовательского сообщения: {error}",
                user_message="Сообщение не может быть пустым.",
                cause=error,
            ) from error


def _format_knowledge_fragment(result: SearchResult) -> str:
    """
    Строка одного фрагмента секции 5 промпта (Sprint 6, задача S6-08,
    §14.8 «данные источников отделены от общих рассуждений») — источник
    первой строкой, текст фрагмента — следующими. `PromptContext.
    knowledge_fragments: Sequence[str]` не несёт структуры — единственное
    место, где источник вообще становится видимым модели, это сама
    строка (никаких отдельных метаданных `PromptBuildResult` не несёт,
    ADR-6.5 не меняет `domain/prompt/`).
    """
    source = result.source
    location = f", стр. {source.page_number}" if source.page_number is not None else ""
    if source.section_title:
        location = f"{location}, раздел «{source.section_title}»"
    return f"Источник: {source.document_title}{location}\n{result.text}"
