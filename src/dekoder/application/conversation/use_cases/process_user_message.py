"""
ProcessUserMessage — центральный use case обработки одного входящего
пользовательского сообщения (Telegram → ProcessUserMessage → LLMProvider →
OpenRouter → ответ), эволюционировавший в Sprint 2 (задача S2-06) —
теперь идентифицирует пользователя, получает/создаёт активный диалог,
сохраняет сообщения и формирует LLM-контекст из истории, а не работает
stateless одним сообщением, как в Sprint 1.

Зависит только от портов (`LLMProvider`, `ConversationRepositoriesFactory`),
DTO собственного модуля и доменных типов (`Message`, `MessageRole`,
`MessageText`, `ModelId`) — ни httpx, ни SQLAlchemy, ни ORM-моделей, ни
Telegram, ни FastAPI, ни URL конкретного провайдера, ни переменных
окружения. Настройки (`default_model`/`system_prompt`/`temperature`/
`max_tokens`) приходят через конструктор — это ответственность
bootstrap-слоя, как и раньше.

Транзакционные границы (backlog_2.md §9, «Транзакционные границы»):

    Транзакция 1 (`_save_user_message`):
        get/create User -> get/create Conversation -> save user Message -> commit

    Вне транзакции:
        load history (отдельная короткая read-only транзакция,
        `_load_history`) -> call LLM (полностью вне какой-либо открытой
        DB-транзакции/сессии)

    Транзакция 2 (`_save_assistant_message`):
        save assistant Message -> commit

Каждая из трёх коротких транзакций — отдельный вызов `self._repositories()`
(`ConversationRepositoriesFactory`, `application/conversation/ports.py`) —
отдельная, независимая `AsyncSession` под капотом (bootstrap-реализация:
`session_scope()`, задача S2-01). Ни одна из них не остаётся открытой во
время сетевого вызова `LLMProvider.generate()` — критическое требование
задачи S2-06.

Профили/Prompt Engine/память/RAG сюда не входят — следующие спринты.
Команды `/new`/`/clear` не входят — отдельные use case (`StartNewConversation`/
`ClearConversation`, следующая задача Sprint 2), `ProcessUserMessage` не
анализирует текст сообщения на предмет команд управления диалогом.

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
    LLMMessage,
    LLMRequest,
    ProcessUserMessageCommand,
    ProcessUserMessageResult,
    TokenUsage,
)
from dekoder.application.conversation.ports import ConversationRepositoriesFactory, LLMProvider
from dekoder.domain.conversation.entities import Message, MessageRole
from dekoder.domain.conversation.value_objects import MessageText, ModelId
from dekoder.shared.errors import ValidationError


class ProcessUserMessage:
    def __init__(
        self,
        llm_provider: LLMProvider,
        repositories: ConversationRepositoriesFactory,
        default_model: ModelId,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        self._llm_provider = llm_provider
        self._repositories = repositories
        self._default_model = default_model
        self._system_prompt = system_prompt
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

        conversation_id = await self._save_user_message(command.telegram_user_id, message_text)
        history = await self._load_history(conversation_id)

        request = LLMRequest(
            system_prompt=self._system_prompt,
            messages=[LLMMessage(role=message.role.value, content=message.content) for message in history],
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
        )

    async def _save_user_message(self, telegram_user_id: int, message_text: MessageText) -> UUID:
        """
        Транзакция 1 (backlog_2.md §9): получить/создать пользователя,
        получить/создать его активный диалог, сохранить сообщение
        пользователя — всё поверх ОДНОЙ короткоживущей транзакции,
        завершаемой commit'ом при выходе из `async with` (или rollback'ом
        при любой ошибке, включая ошибку сохранения сообщения — LLM в
        этом случае не вызывается, см. докстринг модуля).
        """
        async with self._repositories() as repositories:
            user = await repositories.users.get_or_create_by_telegram_user_id(telegram_user_id)
            conversation = await repositories.conversations.get_or_create_active(user.id)
            user_message = self._build_message(conversation.id, MessageRole.USER, message_text.value)
            await repositories.messages.save(user_message)
            return conversation.id

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
