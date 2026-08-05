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

Prompt Engine/память/RAG-контент сюда не входят (Этапы 7-8 заполнят
всегда-пустые `PromptContext.confirmed_memory_facts`/`knowledge_fragments`
— этот use case их пока не собирает). Команды `/new`/`/clear` не входят —
отдельные use case (`StartNewConversation`/`ClearConversation`).

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

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from dekoder.application.conversation.dto import (
    LLMRequest,
    ProcessUserMessageCommand,
    ProcessUserMessageResult,
    TokenUsage,
)
from dekoder.application.conversation.ports import ConversationRepositoriesFactory, LLMProvider
from dekoder.application.prompt.ports import PromptBuilder
from dekoder.domain.conversation.entities import Message, MessageRole
from dekoder.domain.conversation.value_objects import MessageText, ModelId
from dekoder.domain.profile.entities import UserProfile
from dekoder.domain.prompt.value_objects import PromptContext
from dekoder.shared.errors import ValidationError


class ProcessUserMessage:
    def __init__(
        self,
        llm_provider: LLMProvider,
        repositories: ConversationRepositoriesFactory,
        prompt_builder: PromptBuilder,
        default_model: ModelId,
        temperature: float,
        max_tokens: int,
    ) -> None:
        self._llm_provider = llm_provider
        self._repositories = repositories
        self._prompt_builder = prompt_builder
        self._default_model = default_model
        self._temperature = temperature
        self._max_tokens = max_tokens
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
        model_id = command.model_id if command.model_id is not None else self._default_model

        conversation_id, profile = await self._save_user_message(command.telegram_user_id, message_text)
        history = await self._load_history(conversation_id)

        context = PromptContext(profile=profile, dialogue_history=history)
        build_result = self._prompt_builder.build(context)

        request = LLMRequest(
            system_prompt=build_result.system_prompt,
            messages=build_result.messages,
            model_id=model_id,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
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

    async def _save_user_message(self, telegram_user_id: int, message_text: MessageText) -> tuple[UUID, UserProfile]:
        """
        Транзакция 1 (backlog_2.md §9): получить/создать пользователя,
        получить/создать его активный диалог, прочитать его активный
        профиль (Sprint 3, задача S3-07, ADR-3.3 — тем же вызовом
        `self._repositories()`, не отдельной транзакцией), сохранить
        сообщение пользователя — всё поверх ОДНОЙ короткоживущей
        транзакции, завершаемой commit'ом при выходе из `async with`
        (или rollback'ом при любой ошибке, включая ошибку сохранения
        сообщения — LLM в этом случае не вызывается, см. докстринг
        модуля).

        Возвращает `(conversation_id, profile)` (Sprint 4, задача S4-07,
        ADR-4.8) — раньше (Sprint 2/3) возвращался уже вычисленный
        `system_instruction: str` с fallback-логикой внутри этого use
        case; теперь этот use case передаёт весь `UserProfile` как есть,
        а построение системной инструкции (и fallback на пустую строку,
        ADR-4.7) — ответственность `PromptBuilder`/секции 3 Prompt
        Engine, не здесь.
        """
        async with self._repositories() as repositories:
            user = await repositories.users.get_or_create_by_telegram_user_id(telegram_user_id)
            conversation = await repositories.conversations.get_or_create_active(user.id)
            profile = await repositories.profiles.get_active_profile(user.id)
            user_message = self._build_message(conversation.id, MessageRole.USER, message_text.value)
            await repositories.messages.save(user_message)
            return conversation.id, profile

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
