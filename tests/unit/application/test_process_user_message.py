"""
Тесты ProcessUserMessage (application/conversation/use_cases/process_user_message.py).

Sprint 2 (задача S2-06): use case теперь идентифицирует пользователя,
получает/создаёт активный диалог, сохраняет сообщения и формирует
LLM-контекст из истории — тесты используют fake-репозитории (in-memory,
без SQLAlchemy) + fake LLMProvider, как и требует backlog_2.md §9
(«unit-тесты не должны использовать SQLAlchemy»). Интеграционный тест на
реальном persistence-потоке — tests/integration/test_process_user_message_persistence.py.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from tests.support.fake_conversation_repositories import (
    FakeMemoryRepository,
    FakeModelSelectionRepository,
    FakeProfileRepository,
    make_default_profile,
)
from tests.support.fake_knowledge_repositories import FakeKnowledgeSearchService
from tests.support.fake_model_catalog import FakeModelCatalogRepository, default_test_catalog, make_ai_model
from tests.support.prompt_engine import make_test_prompt_builder

from dekoder.application.conversation.dto import (
    LLMRequest,
    LLMResponse,
    ProcessUserMessageCommand,
)
from dekoder.application.conversation.ports import ConversationRepositories, ConversationRepositoriesFactory
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.application.knowledge.ports import KnowledgeSearchService
from dekoder.application.model_catalog.ports import ModelCatalogRepository
from dekoder.application.prompt.ports import PromptBuilder
from dekoder.domain.conversation.entities import Conversation, Message, MessageRole
from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.domain.knowledge.search import SearchResult, SourceReference
from dekoder.domain.memory.entities import MemoryRecord
from dekoder.domain.memory.value_objects import (
    MemoryCategory,
    MemoryConfidence,
    MemorySource,
    MemoryStatus,
)
from dekoder.domain.model_catalog.enums import ModelAvailability
from dekoder.domain.user.entities import User
from dekoder.shared.domain.identifiers import CorrelationId
from dekoder.shared.errors import InfrastructureError, LLMProviderError, ValidationError
from dekoder.shared.logging import clear_request_context, configure_logging


def _make_memory_record(user_id: UUID, **overrides: object) -> MemoryRecord:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "id": uuid4(),
        "user_id": user_id,
        "text": "Работает Python-разработчиком.",
        "category": MemoryCategory.FACT,
        "source": MemorySource.USER_EXPLICIT,
        "status": MemoryStatus.CONFIRMED,
        "confidence": MemoryConfidence.MEDIUM,
        "is_sensitive": False,
        "expires_at": None,
        "updated_by": "user",
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return MemoryRecord(**defaults)  # type: ignore[arg-type]


class FakeUserRepository:
    """In-memory fake порта UserRepository (application/user/ports.py) — без SQLAlchemy."""

    def __init__(self) -> None:
        self._by_telegram_user_id: dict[int, User] = {}
        self.get_or_create_calls = 0

    async def get_by_id(self, user_id: UUID) -> User | None:
        for user in self._by_telegram_user_id.values():
            if user.id == user_id:
                return user
        return None

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> User | None:
        return self._by_telegram_user_id.get(telegram_user_id)

    async def save(self, user: User) -> User:
        self._by_telegram_user_id[user.telegram_user_id] = user
        return user

    async def get_or_create_by_telegram_user_id(self, telegram_user_id: int) -> User:
        self.get_or_create_calls += 1
        existing = self._by_telegram_user_id.get(telegram_user_id)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        user = User(id=uuid4(), telegram_user_id=telegram_user_id, created_at=now, updated_at=now)
        self._by_telegram_user_id[telegram_user_id] = user
        return user


class FakeConversationRepository:
    """In-memory fake порта ConversationRepository (application/conversation/ports.py)."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, Conversation] = {}
        self.get_or_create_calls = 0

    async def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        return self._by_id.get(conversation_id)

    async def get_active_by_user_id(self, user_id: UUID) -> Conversation | None:
        for conversation in self._by_id.values():
            if conversation.user_id == user_id and conversation.is_active:
                return conversation
        return None

    async def save(self, conversation: Conversation) -> Conversation:
        self._by_id[conversation.id] = conversation
        return conversation

    async def close(self, conversation: Conversation) -> Conversation:
        self._by_id[conversation.id] = conversation
        return conversation

    async def get_or_create_active(self, user_id: UUID) -> Conversation:
        self.get_or_create_calls += 1
        existing = await self.get_active_by_user_id(user_id)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        conversation = Conversation(id=uuid4(), user_id=user_id, created_at=now, updated_at=now, closed_at=None)
        self._by_id[conversation.id] = conversation
        return conversation


class FakeMessageRepository:
    """
    In-memory fake порта MessageRepository (application/conversation/ports.py).

    `fail_on_save_call(n, error)` позволяет тестам смоделировать сбой
    сохранения N-го по счёту сообщения (1 — пользовательское, 2 —
    ассистента, при обычном потоке одного вызова `execute()`).
    """

    def __init__(self) -> None:
        self._by_conversation: dict[UUID, list[Message]] = {}
        self.saved: list[Message] = []
        self.save_calls = 0
        self.history_calls: list[UUID] = []
        self._fail_on_call_number: int | None = None
        self._error: Exception | None = None

    def fail_on_save_call(self, call_number: int, error: Exception) -> None:
        self._fail_on_call_number = call_number
        self._error = error

    async def save(self, message: Message) -> Message:
        self.save_calls += 1
        if self._fail_on_call_number == self.save_calls:
            assert self._error is not None
            raise self._error
        self._by_conversation.setdefault(message.conversation_id, []).append(message)
        self.saved.append(message)
        return message

    async def history(self, conversation_id: UUID) -> list[Message]:
        self.history_calls.append(conversation_id)
        return list(self._by_conversation.get(conversation_id, []))

    async def clear(self, conversation_id: UUID) -> int:
        count = len(self._by_conversation.get(conversation_id, []))
        self._by_conversation[conversation_id] = []
        return count


class FakeLLMProvider:
    """Fake без наследования от LLMProvider — Protocol допускает структурную типизацию."""

    def __init__(self, response: LLMResponse | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.received_requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.received_requests.append(request)
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


def _make_repositories_factory(
    users: FakeUserRepository,
    conversations: FakeConversationRepository,
    messages: FakeMessageRepository,
    profiles: FakeProfileRepository | None = None,
    memory: FakeMemoryRepository | None = None,
    model_selection: FakeModelSelectionRepository | None = None,
) -> ConversationRepositoriesFactory:
    profiles = profiles if profiles is not None else FakeProfileRepository()
    memory = memory if memory is not None else FakeMemoryRepository()
    model_selection = model_selection if model_selection is not None else FakeModelSelectionRepository()

    @asynccontextmanager
    async def _factory() -> AsyncIterator[ConversationRepositories]:
        yield ConversationRepositories(
            users=users,
            conversations=conversations,
            messages=messages,
            profiles=profiles,
            memory=memory,
            model_selection=model_selection,
        )

    return _factory


def _make_response(text: str = "Здравствуйте!", model_id: str = "openai/gpt-4o-mini") -> LLMResponse:
    return LLMResponse(
        text=text,
        provider_id=ProviderId("test-provider"),
        model_id=ModelId(model_id),
        input_tokens=10,
        output_tokens=5,
        duration_ms=42.0,
    )


def _make_command(
    text: str = "Привет!", telegram_user_id: int = 123, model_id: ModelId | None = None
) -> ProcessUserMessageCommand:
    return ProcessUserMessageCommand(
        telegram_user_id=telegram_user_id,
        message_text=text,
        correlation_id=CorrelationId("corr-1"),
        model_id=model_id,
    )


class _Repos:
    __slots__ = ("users", "conversations", "messages", "profiles", "memory", "model_selection")

    def __init__(
        self,
        users: FakeUserRepository,
        conversations: FakeConversationRepository,
        messages: FakeMessageRepository,
        profiles: FakeProfileRepository,
        memory: FakeMemoryRepository,
        model_selection: FakeModelSelectionRepository,
    ) -> None:
        self.users = users
        self.conversations = conversations
        self.messages = messages
        self.profiles = profiles
        self.memory = memory
        self.model_selection = model_selection


def _make_use_case(
    provider: FakeLLMProvider,
    default_model: str = "openai/gpt-4o-mini",
    prompt_builder: PromptBuilder | None = None,
    users: FakeUserRepository | None = None,
    conversations: FakeConversationRepository | None = None,
    messages: FakeMessageRepository | None = None,
    profiles: FakeProfileRepository | None = None,
    memory: FakeMemoryRepository | None = None,
    model_selection: FakeModelSelectionRepository | None = None,
    knowledge_search: KnowledgeSearchService | None = None,
    model_catalog: ModelCatalogRepository | None = None,
) -> tuple[ProcessUserMessage, _Repos]:
    users = users if users is not None else FakeUserRepository()
    conversations = conversations if conversations is not None else FakeConversationRepository()
    messages = messages if messages is not None else FakeMessageRepository()
    profiles = profiles if profiles is not None else FakeProfileRepository()
    memory = memory if memory is not None else FakeMemoryRepository()
    model_selection = model_selection if model_selection is not None else FakeModelSelectionRepository()
    knowledge_search = knowledge_search if knowledge_search is not None else FakeKnowledgeSearchService()
    model_catalog = model_catalog if model_catalog is not None else default_test_catalog(default_model)
    factory = _make_repositories_factory(users, conversations, messages, profiles, memory, model_selection)
    use_case = ProcessUserMessage(
        llm_provider=provider,
        repositories=factory,
        prompt_builder=prompt_builder if prompt_builder is not None else make_test_prompt_builder(),
        knowledge_search=knowledge_search,
        model_catalog=model_catalog,
        default_model=ModelId(default_model),
        temperature=0.7,
        max_tokens=512,
        max_relevant_memory=5,
    )
    return use_case, _Repos(users, conversations, messages, profiles, memory, model_selection)


class TestNewUser:
    """Обязательный сценарий 1 (backlog_2_tasks.md, S2-06): новый пользователь."""

    async def test_creates_user_and_active_conversation_and_returns_response(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case, repos = _make_use_case(provider)

        result = await use_case.execute(_make_command(telegram_user_id=999))

        assert result.response_text == "Здравствуйте!"
        stored_user = await repos.users.get_by_telegram_user_id(999)
        assert stored_user is not None
        stored_conversation = await repos.conversations.get_active_by_user_id(stored_user.id)
        assert stored_conversation is not None
        assert result.conversation_id == stored_conversation.id

    async def test_saves_user_message_before_calling_llm(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case, repos = _make_use_case(provider)

        await use_case.execute(_make_command(text="Привет!", telegram_user_id=999))

        saved_roles = [message.role for message in repos.messages.saved]
        assert MessageRole.USER in saved_roles

    async def test_llm_receives_history_containing_current_message(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider)

        await use_case.execute(_make_command(text="Привет!"))

        request = provider.received_requests[0]
        assert [m.role for m in request.messages] == ["user"]
        assert request.messages[0].content == "Привет!"

    async def test_saves_assistant_message_after_successful_response(self) -> None:
        provider = FakeLLMProvider(response=_make_response("Здравствуйте!"))
        use_case, repos = _make_use_case(provider)

        result = await use_case.execute(_make_command())

        assistant_messages = [m for m in repos.messages.saved if m.role == MessageRole.ASSISTANT]
        assert len(assistant_messages) == 1
        assert assistant_messages[0].content == "Здравствуйте!"
        assert result.message_id == assistant_messages[0].id

    async def test_returns_result_built_from_llm_response(self) -> None:
        response = _make_response()
        provider = FakeLLMProvider(response=response)
        use_case, _ = _make_use_case(provider)

        result = await use_case.execute(_make_command())

        assert result.response_text == response.text
        assert result.provider_id == response.provider_id
        assert result.model_id == response.model_id
        assert result.duration_ms == response.duration_ms
        assert result.usage is not None
        assert result.usage.input_tokens == response.input_tokens
        assert result.usage.output_tokens == response.output_tokens


class TestExistingUserAndActiveConversation:
    """Обязательный сценарий 2: существующий пользователь и активный диалог."""

    async def test_does_not_create_new_user_or_conversation_on_second_message(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case, repos = _make_use_case(provider)

        await use_case.execute(_make_command(text="Привет!", telegram_user_id=42))
        first_user = await repos.users.get_by_telegram_user_id(42)
        assert first_user is not None
        first_conversation = await repos.conversations.get_active_by_user_id(first_user.id)
        assert first_conversation is not None

        result = await use_case.execute(_make_command(text="Как дела?", telegram_user_id=42))

        second_user = await repos.users.get_by_telegram_user_id(42)
        assert second_user == first_user
        assert result.conversation_id == first_conversation.id

    async def test_history_continues_in_the_same_conversation(self) -> None:
        provider1 = FakeLLMProvider(response=_make_response("Ответ 1"))
        use_case1, repos = _make_use_case(provider1)
        await use_case1.execute(_make_command(text="Сообщение 1", telegram_user_id=7))

        provider2 = FakeLLMProvider(response=_make_response("Ответ 2"))
        use_case2, _ = _make_use_case(
            provider2, users=repos.users, conversations=repos.conversations, messages=repos.messages
        )
        await use_case2.execute(_make_command(text="Сообщение 2", telegram_user_id=7))

        second_request = provider2.received_requests[0]
        contents = [m.content for m in second_request.messages]
        assert contents == ["Сообщение 1", "Ответ 1", "Сообщение 2"]


class TestHistoryOrderingAndDeduplication:
    """Обязательные сценарии 3 и 4: порядок истории, отсутствие дублирования текущего сообщения."""

    async def test_history_passed_to_llm_is_chronological_and_current_message_is_last(self) -> None:
        provider = FakeLLMProvider(response=_make_response("Ответ 1"))
        use_case, repos = _make_use_case(provider)

        await use_case.execute(_make_command(text="Первое", telegram_user_id=1))

        provider2 = FakeLLMProvider(response=_make_response("Ответ 2"))
        use_case2, _ = _make_use_case(
            provider2, users=repos.users, conversations=repos.conversations, messages=repos.messages
        )
        await use_case2.execute(_make_command(text="Второе", telegram_user_id=1))

        request = provider2.received_requests[0]
        assert [m.content for m in request.messages] == ["Первое", "Ответ 1", "Второе"]
        assert request.messages[-1].content == "Второе"

    async def test_current_user_message_is_not_duplicated_in_llm_context(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider)

        await use_case.execute(_make_command(text="Привет!"))

        request = provider.received_requests[0]
        occurrences = [m for m in request.messages if m.content == "Привет!"]
        assert len(occurrences) == 1


class TestAssistantMessageAppearsOnlyAfterSuccess:
    """Обязательные сценарии 5 и 6: ответ ассистента появляется в истории только после успешного вызова LLM."""

    async def test_assistant_message_absent_before_llm_call_completes(self) -> None:
        messages = FakeMessageRepository()
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, messages=messages)

        await use_case.execute(_make_command())

        # К моменту сохранения пользовательского сообщения (до вызова LLM)
        # ассистентского сообщения ещё не было — проверяем по итоговому
        # состоянию: единственное сообщение до второго save — user.
        assert messages.save_calls == 2
        assert [m.role for m in messages.saved] == [MessageRole.USER, MessageRole.ASSISTANT]

    async def test_next_request_sees_previous_assistant_message_in_history(self) -> None:
        provider1 = FakeLLMProvider(response=_make_response("Первый ответ"))
        use_case, repos = _make_use_case(provider1)
        await use_case.execute(_make_command(text="Вопрос 1", telegram_user_id=55))

        provider2 = FakeLLMProvider(response=_make_response("Второй ответ"))
        use_case2, _ = _make_use_case(
            provider2, users=repos.users, conversations=repos.conversations, messages=repos.messages
        )
        await use_case2.execute(_make_command(text="Вопрос 2", telegram_user_id=55))

        request = provider2.received_requests[0]
        assert "Первый ответ" in [m.content for m in request.messages]


class TestEmptyText:
    async def test_empty_text_raises_validation_error(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider)

        with pytest.raises(ValidationError):
            await use_case.execute(_make_command(text=""))

    async def test_whitespace_only_text_raises_validation_error(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider)

        with pytest.raises(ValidationError):
            await use_case.execute(_make_command(text="   "))

    async def test_empty_text_does_not_call_provider(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider)

        with pytest.raises(ValidationError):
            await use_case.execute(_make_command(text=""))

        assert provider.received_requests == []


class TestModelResolution:
    """
    Sprint 7, задача S7-06 (ADR-7.7): разрешение активной модели по
    приоритету `command.model_id` → персональный выбор → умолчание, с
    молчаливым логируемым откатом при недоступности выбранной модели.
    """

    async def test_uses_default_model_when_command_has_none(self) -> None:
        """Регрессия поведения Sprint 1-6: нет ни override, ни персонального выбора → `self._default_model`."""
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, default_model="openai/gpt-4o-mini")

        await use_case.execute(_make_command(model_id=None))

        assert provider.received_requests[0].model_id == ModelId("openai/gpt-4o-mini")

    async def test_uses_model_from_command_when_provided(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, default_model="openai/gpt-4o-mini")

        await use_case.execute(_make_command(model_id=ModelId("anthropic/claude-3-haiku")))

        assert provider.received_requests[0].model_id == ModelId("anthropic/claude-3-haiku")

    async def test_personal_selection_is_used_when_command_has_none(self) -> None:
        """AC-1 (S7-06): персональный выбор доступной модели применяется, когда нет `command.model_id`."""
        selected_model = make_ai_model(
            "anthropic/claude-3.5-sonnet",
            availability=ModelAvailability.AVAILABLE,
            temperature=0.3,
            max_tokens=4096,
        )
        catalog = FakeModelCatalogRepository([make_ai_model("openai/gpt-4o-mini"), selected_model])
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(1001)
        model_selection = FakeModelSelectionRepository({user.id: selected_model.model_id})
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, users=users, model_selection=model_selection, model_catalog=catalog)

        await use_case.execute(_make_command(telegram_user_id=1001, model_id=None))

        request = provider.received_requests[0]
        assert request.model_id == selected_model.model_id
        assert request.temperature == 0.3
        assert request.max_tokens == 4096

    async def test_explicit_override_wins_over_personal_selection(self) -> None:
        """AC-2 (S7-06): явный `command.model_id` побеждает персональный выбор; override не проверяется каталогом."""
        selected_model = make_ai_model("anthropic/claude-3.5-sonnet", availability=ModelAvailability.AVAILABLE)
        # Каталог не содержит override-модель — override не проверяется
        # через каталог (ADR-7.7), поэтому это не должно приводить к
        # откату/ошибке.
        catalog = FakeModelCatalogRepository([make_ai_model("openai/gpt-4o-mini"), selected_model])
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(1002)
        model_selection = FakeModelSelectionRepository({user.id: selected_model.model_id})
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, users=users, model_selection=model_selection, model_catalog=catalog)

        override_model_id = ModelId("does-not-exist-in-catalog/override-model")
        await use_case.execute(_make_command(telegram_user_id=1002, model_id=override_model_id))

        assert provider.received_requests[0].model_id == override_model_id

    async def test_unavailable_personal_selection_falls_back_to_default_and_logs_warning(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AC-3 (S7-06): персональный выбор указывает на UNAVAILABLE-модель → откат на `self._default_model`, лог."""
        clear_request_context()
        configure_logging(environment="test")
        unavailable_model = make_ai_model("anthropic/claude-3-haiku", availability=ModelAvailability.UNAVAILABLE)
        catalog = FakeModelCatalogRepository([make_ai_model("openai/gpt-4o-mini"), unavailable_model])
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(1003)
        model_selection = FakeModelSelectionRepository({user.id: unavailable_model.model_id})
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(
            provider,
            default_model="openai/gpt-4o-mini",
            users=users,
            model_selection=model_selection,
            model_catalog=catalog,
        )

        await use_case.execute(_make_command(telegram_user_id=1003, model_id=None))

        assert provider.received_requests[0].model_id == ModelId("openai/gpt-4o-mini")

        log_lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
        fallback_entries = [line for line in log_lines if line.get("event") == "model_selection_fallback"]
        assert len(fallback_entries) == 1
        assert fallback_entries[0]["requested_model_id"] == "anthropic/claude-3-haiku"
        assert fallback_entries[0]["fallback_model_id"] == "openai/gpt-4o-mini"
        assert fallback_entries[0]["user_id"] == str(user.id)
        assert fallback_entries[0]["level"] == "warning"
        clear_request_context()

    async def test_unknown_model_in_catalog_also_falls_back_to_default(self) -> None:
        """Откат применяется и когда персональный выбор указывает на `model_id`, которого больше нет в каталоге."""
        catalog = FakeModelCatalogRepository([make_ai_model("openai/gpt-4o-mini")])
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(1004)
        model_selection = FakeModelSelectionRepository({user.id: ModelId("removed/model")})
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(
            provider,
            default_model="openai/gpt-4o-mini",
            users=users,
            model_selection=model_selection,
            model_catalog=catalog,
        )

        await use_case.execute(_make_command(telegram_user_id=1004, model_id=None))

        assert provider.received_requests[0].model_id == ModelId("openai/gpt-4o-mini")


class TestLLMError:
    """Обязательный сценарий 7: ошибка LLM."""

    async def test_provider_error_propagates(self) -> None:
        error = LLMProviderError(
            message="LLM provider timeout",
            user_message="Не удалось получить ответ от модели, попробуйте позже.",
        )
        provider = FakeLLMProvider(error=error)
        use_case, _ = _make_use_case(provider)

        with pytest.raises(LLMProviderError) as exc_info:
            await use_case.execute(_make_command())

        assert exc_info.value is error

    async def test_user_message_remains_saved_and_assistant_message_absent(self) -> None:
        error = LLMProviderError(message="boom", user_message="Ошибка модели.")
        provider = FakeLLMProvider(error=error)
        messages = FakeMessageRepository()
        use_case, _ = _make_use_case(provider, messages=messages)

        with pytest.raises(LLMProviderError):
            await use_case.execute(_make_command())

        assert [m.role for m in messages.saved] == [MessageRole.USER]

    async def test_does_not_leave_the_repository_in_a_pending_write_state(self) -> None:
        """Нет открытой «транзакции» — вторая обработка того же пользователя проходит штатно."""
        error = LLMProviderError(message="boom", user_message="Ошибка модели.")
        provider_failing = FakeLLMProvider(error=error)
        use_case, repos = _make_use_case(provider_failing)

        with pytest.raises(LLMProviderError):
            await use_case.execute(_make_command(telegram_user_id=321))

        provider_ok = FakeLLMProvider(response=_make_response())
        use_case_ok, _ = _make_use_case(
            provider_ok, users=repos.users, conversations=repos.conversations, messages=repos.messages
        )
        result = await use_case_ok.execute(_make_command(telegram_user_id=321))

        assert result.response_text == "Здравствуйте!"


class TestUserMessageSaveError:
    """Обязательный сценарий 8: ошибка сохранения пользовательского сообщения."""

    async def test_llm_is_not_called_when_saving_user_message_fails(self) -> None:
        messages = FakeMessageRepository()
        messages.fail_on_save_call(
            1,
            InfrastructureError(message="db down", user_message="Не удалось обработать запрос, попробуйте позже."),
        )
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, messages=messages)

        with pytest.raises(InfrastructureError):
            await use_case.execute(_make_command())

        assert provider.received_requests == []

    async def test_error_propagates_to_caller(self) -> None:
        messages = FakeMessageRepository()
        error = InfrastructureError(message="db down", user_message="Не удалось обработать запрос, попробуйте позже.")
        messages.fail_on_save_call(1, error)
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, messages=messages)

        with pytest.raises(InfrastructureError) as exc_info:
            await use_case.execute(_make_command())

        assert exc_info.value is error


class TestAssistantMessageSaveError:
    """Обязательный сценарий 9: ошибка сохранения ответа ассистента."""

    async def test_user_message_remains_saved_and_operation_fails(self) -> None:
        messages = FakeMessageRepository()
        messages.fail_on_save_call(
            2,
            InfrastructureError(message="db down", user_message="Не удалось обработать запрос, попробуйте позже."),
        )
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, messages=messages)

        with pytest.raises(InfrastructureError):
            await use_case.execute(_make_command())

        assert [m.role for m in messages.saved] == [MessageRole.USER]

    async def test_llm_is_not_called_again_after_assistant_save_failure(self) -> None:
        messages = FakeMessageRepository()
        messages.fail_on_save_call(
            2,
            InfrastructureError(message="db down", user_message="Не удалось обработать запрос, попробуйте позже."),
        )
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, messages=messages)

        with pytest.raises(InfrastructureError):
            await use_case.execute(_make_command())

        assert len(provider.received_requests) == 1


class TestResultType:
    """Обязательный сценарий 10: use case возвращает application-тип, не ORM/сырой SDK response."""

    async def test_result_is_process_user_message_result_with_plain_types(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider)

        result = await use_case.execute(_make_command())

        assert type(result).__name__ == "ProcessUserMessageResult"
        assert isinstance(result.response_text, str)
        assert isinstance(result.conversation_id, UUID)
        assert isinstance(result.message_id, UUID)


class TestPersonalization:
    """
    Sprint 3, задача S3-07 (ADR-3.3): системная инструкция LLMRequest
    берётся из активного профиля пользователя.

    Sprint 4 (задача S4-07, ADR-4.7): собранный `system_prompt` больше не
    РАВЕН `profile.system_instruction` как есть — это склейка секций 1
    (базовая инструкция, безусловная для любого профиля), 2
    (правила безопасности), 3 (параметры профиля, включая
    `system_instruction`) и 8 (формат ответа). Поэтому тесты проверяют
    вхождение (`in`), не равенство — и используют реальный
    `PromptBuilder` (`tests.support.prompt_engine.make_test_prompt_builder`,
    те же сид-шаблоны, что и в проде), а не `default_system_prompt`
    (параметр удалён вместе с `_DEFAULT_SYSTEM_PROMPT`, ADR-4.7).
    """

    # Совпадает с текстом сид-шаблона `base_instruction`
    # (`infrastructure/prompts/templates/base_instruction.txt`) — прежней
    # константой `_DEFAULT_SYSTEM_PROMPT` (`bootstrap/container.py`) до
    # её удаления в этой задаче (S4-07/ADR-4.7).
    _BASE_INSTRUCTION_TEXT = "Ты — персональный ассистент «Декодер». Отвечай кратко и по делу."

    async def test_system_prompt_contains_active_profile_instruction(self) -> None:
        profile = make_default_profile(name="Экспертный")
        object.__setattr__(profile, "system_instruction", "Отвечай точно и по делу, как эксперт.")
        profiles = FakeProfileRepository([profile])
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, profiles=profiles)

        await use_case.execute(_make_command())

        request = provider.received_requests[0]
        assert "Отвечай точно и по делу, как эксперт." in request.system_prompt
        # Секция 1 (базовая инструкция) присутствует безусловно, для
        # любого профиля — не заменяется инструкцией профиля (ADR-4.7).
        assert self._BASE_INSTRUCTION_TEXT in request.system_prompt

    async def test_different_users_with_different_selected_profiles_get_different_system_prompt(self) -> None:
        default_profile = make_default_profile(name="Деловой")
        object.__setattr__(default_profile, "system_instruction", "Кратко и по делу.")
        creative_profile = make_default_profile(is_default=False, name="Креативный")
        object.__setattr__(creative_profile, "system_instruction", "Отвечай образно, с метафорами.")
        profiles = FakeProfileRepository([default_profile, creative_profile])
        users = FakeUserRepository()
        await users.get_or_create_by_telegram_user_id(111)
        user_b = await users.get_or_create_by_telegram_user_id(222)
        await profiles.select_profile(user_b.id, creative_profile.id)

        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, users=users, profiles=profiles)

        await use_case.execute(_make_command(telegram_user_id=111))
        await use_case.execute(_make_command(telegram_user_id=222))

        first_prompt = provider.received_requests[0].system_prompt
        second_prompt = provider.received_requests[1].system_prompt
        assert "Кратко и по делу." in first_prompt
        assert "Отвечай образно, с метафорами." in second_prompt
        assert first_prompt != second_prompt

    async def test_base_instruction_present_even_when_profile_instruction_is_blank(self) -> None:
        """
        Sprint 4, задача S4-07 (ADR-4.7): узкий эквивалент прежнего теста
        Sprint 2/3 «fallback на default_system_prompt при пустом
        system_instruction» — домен не допускает создать `UserProfile` с
        пустой `system_instruction` (`__post_init__`), поэтому тест
        обходит это через `object.__setattr__`, как и раньше; но
        ожидаемое поведение изменилось (ADR-4.7): вместо fallback на
        отдельную default-строку теперь просто присутствует секция 1
        (безусловна для любого профиля), а секция 3 не подставляет вместо
        пустой `system_instruction` ничего — не бросает и не превращает
        весь промпт в пустую строку.
        """
        profile = make_default_profile(name="Пустой")
        object.__setattr__(profile, "system_instruction", "   ")
        profiles = FakeProfileRepository([profile])
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, profiles=profiles)

        await use_case.execute(_make_command())

        request = provider.received_requests[0]
        assert self._BASE_INSTRUCTION_TEXT in request.system_prompt
        assert request.system_prompt.strip()


class TestMemoryIntegration:
    """
    Sprint 5, задача S5-06 (ADR-5.4/5.6/5.11): `PromptContext.
    confirmed_memory_facts` заполняется реальными данными
    `MemoryRepository.find_relevant`, вызываемого напрямую внутри
    транзакции 1 — не отдельным use case'ом, не отдельной транзакцией.

    Как и `TestPersonalization`, использует реальный `PromptBuilder`
    (`tests.support.prompt_engine.make_test_prompt_builder`) — предмет
    проверки именно содержимое собранного `system_prompt` (ADR-5.11 DoD:
    «интеграционный тест: execute() с реальным PromptBuilder и
    подготовленными записями памяти — system_prompt содержит текст
    факта»), а не факт вызова fake-объекта.
    """

    async def test_system_prompt_contains_confirmed_memory_fact(self) -> None:
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(900)
        memory = FakeMemoryRepository([_make_memory_record(user.id, text="Живёт в Берлине.")])
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, users=users, memory=memory)

        await use_case.execute(_make_command(telegram_user_id=900))

        request = provider.received_requests[0]
        assert "Живёт в Берлине." in request.system_prompt

    async def test_pending_and_expired_records_are_excluded(self) -> None:
        """`find_relevant` — единственная точка правила «неподтверждённая/истёкшая память не входит в контекст»."""
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(901)
        pending = _make_memory_record(user.id, text="Черновой факт про кошку.", status=MemoryStatus.PENDING)
        expired = _make_memory_record(
            user.id, text="Просроченный факт про собаку.", expires_at=datetime.now(UTC) - timedelta(days=1)
        )
        memory = FakeMemoryRepository([pending, expired])
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, users=users, memory=memory)

        await use_case.execute(_make_command(telegram_user_id=901))

        request = provider.received_requests[0]
        assert "Черновой факт про кошку." not in request.system_prompt
        assert "Просроченный факт про собаку." not in request.system_prompt

    async def test_empty_memory_still_produces_a_valid_prompt(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider)

        await use_case.execute(_make_command())

        request = provider.received_requests[0]
        assert request.system_prompt.strip()

    async def test_find_relevant_is_called_within_the_existing_three_transactions(self) -> None:
        """
        AC-3: `find_relevant` вызывается внутри уже существующей
        транзакции 1 — количество вызовов `self._repositories()` за одно
        `execute()` не увеличилось относительно Sprint 4 (по-прежнему 3:
        сохранение сообщения пользователя+профиль+память, загрузка
        истории, сохранение сообщения ассистента).
        """
        users = FakeUserRepository()
        user = await users.get_or_create_by_telegram_user_id(902)
        memory = FakeMemoryRepository([_make_memory_record(user.id)])
        inner_factory = _make_repositories_factory(
            users, FakeConversationRepository(), FakeMessageRepository(), memory=memory
        )

        call_count = 0

        @asynccontextmanager
        async def _counting_factory() -> AsyncIterator[ConversationRepositories]:
            nonlocal call_count
            call_count += 1
            async with inner_factory() as repositories:
                yield repositories

        provider = FakeLLMProvider(response=_make_response())
        use_case = ProcessUserMessage(
            llm_provider=provider,
            repositories=_counting_factory,
            prompt_builder=make_test_prompt_builder(),
            knowledge_search=FakeKnowledgeSearchService(),
            model_catalog=default_test_catalog("openai/gpt-4o-mini"),
            default_model=ModelId("openai/gpt-4o-mini"),
            temperature=0.7,
            max_tokens=512,
            max_relevant_memory=5,
        )

        await use_case.execute(_make_command(telegram_user_id=902))

        # Поиск по базе знаний — вне DB-транзакций (ADR-6.4, Sprint 6):
        # число вызовов self._repositories() не увеличилось относительно
        # Sprint 5, несмотря на добавление RAG в execute().
        assert call_count == 3


class TestKnowledgeIntegration:
    """
    Sprint 6, задача S6-08 (ADR-6.4/6.5): `PromptContext.knowledge_fragments`
    заполняется результатами `KnowledgeSearchService.search`, вызываемого
    напрямую (без отдельного use case'а) вне DB-транзакций — в отличие от
    `TestMemoryIntegration`, поиск не проходит через `_repositories()`.

    Как и `TestMemoryIntegration`, использует реальный `PromptBuilder`
    (`tests.support.prompt_engine.make_test_prompt_builder`) — предмет
    проверки именно содержимое собранного `system_prompt`.
    """

    async def test_system_prompt_contains_found_fragment_text(self) -> None:
        result = SearchResult(
            text="Гарантия действует 24 месяца.",
            score=0.9,
            source=SourceReference(
                document_id=uuid4(),
                document_title="Условия гарантии",
                chunk_index=0,
                section_title=None,
                page_number=None,
            ),
        )
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, knowledge_search=FakeKnowledgeSearchService([result]))

        await use_case.execute(_make_command())

        request = provider.received_requests[0]
        assert "Гарантия действует 24 месяца." in request.system_prompt
        assert "Условия гарантии" in request.system_prompt

    async def test_search_is_called_with_the_users_message_text(self) -> None:
        knowledge_search = FakeKnowledgeSearchService()
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, knowledge_search=knowledge_search)

        await use_case.execute(_make_command(text="Какая гарантия на товар?"))

        assert knowledge_search.search_calls == ["Какая гарантия на товар?"]

    async def test_empty_search_result_still_produces_a_valid_prompt(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, knowledge_search=FakeKnowledgeSearchService([]))

        await use_case.execute(_make_command())

        request = provider.received_requests[0]
        assert request.system_prompt.strip()

    async def test_search_failure_does_not_crash_execute(self) -> None:
        """§14.8: сбой поиска (эмбеддинги/Qdrant недоступны) — «ответ формируется без RAG», не ошибка."""
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, knowledge_search=FakeKnowledgeSearchService(fail=True))

        result = await use_case.execute(_make_command())

        assert result.response_text == "Здравствуйте!"

    async def test_logs_knowledge_search_completed_with_chunks_found(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Sprint 9, S9-06 (ADR-9.6): успешный поиск логируется вместе с числом найденных фрагментов."""
        clear_request_context()
        configure_logging(environment="test")
        result = SearchResult(
            text="Гарантия действует 24 месяца.",
            score=0.9,
            source=SourceReference(
                document_id=uuid4(),
                document_title="Условия гарантии",
                chunk_index=0,
                section_title=None,
                page_number=None,
            ),
        )
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, knowledge_search=FakeKnowledgeSearchService([result]))

        await use_case.execute(_make_command())

        log_lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
        entries = [line for line in log_lines if line.get("event") == "knowledge_search_completed"]
        assert len(entries) == 1
        assert entries[0]["chunks_found"] == 1
        assert isinstance(entries[0]["duration_ms"], (int, float))
        clear_request_context()

    async def test_logs_knowledge_search_completed_even_when_no_results_found(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """ADR-9.6: `chunks_found=0` — штатный исход RAG, не оборачивается в `if results:`."""
        clear_request_context()
        configure_logging(environment="test")
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, knowledge_search=FakeKnowledgeSearchService([]))

        await use_case.execute(_make_command())

        log_lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
        entries = [line for line in log_lines if line.get("event") == "knowledge_search_completed"]
        assert len(entries) == 1
        assert entries[0]["chunks_found"] == 0
        clear_request_context()

    async def test_does_not_log_knowledge_search_completed_on_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        clear_request_context()
        configure_logging(environment="test")
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, knowledge_search=FakeKnowledgeSearchService(fail=True))

        await use_case.execute(_make_command())

        log_lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
        events = [line.get("event") for line in log_lines]
        assert "knowledge_search_completed" not in events
        assert "knowledge_search_failed" in events
        clear_request_context()
