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

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from tests.support.fake_conversation_repositories import FakeProfileRepository, make_default_profile

from dekoder.application.conversation.dto import (
    LLMRequest,
    LLMResponse,
    ProcessUserMessageCommand,
)
from dekoder.application.conversation.ports import ConversationRepositories, ConversationRepositoriesFactory
from dekoder.application.conversation.use_cases.process_user_message import ProcessUserMessage
from dekoder.domain.conversation.entities import Conversation, Message, MessageRole
from dekoder.domain.conversation.value_objects import ModelId, ProviderId
from dekoder.domain.user.entities import User
from dekoder.shared.domain.identifiers import CorrelationId
from dekoder.shared.errors import InfrastructureError, LLMProviderError, ValidationError


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
) -> ConversationRepositoriesFactory:
    profiles = profiles if profiles is not None else FakeProfileRepository()

    @asynccontextmanager
    async def _factory() -> AsyncIterator[ConversationRepositories]:
        yield ConversationRepositories(users=users, conversations=conversations, messages=messages, profiles=profiles)

    return _factory


def _make_response(text: str = "Здравствуйте!", model_id: str = "openai/gpt-4o-mini") -> LLMResponse:
    return LLMResponse(
        text=text,
        provider_id=ProviderId("openrouter"),
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
    __slots__ = ("users", "conversations", "messages", "profiles")

    def __init__(
        self,
        users: FakeUserRepository,
        conversations: FakeConversationRepository,
        messages: FakeMessageRepository,
        profiles: FakeProfileRepository,
    ) -> None:
        self.users = users
        self.conversations = conversations
        self.messages = messages
        self.profiles = profiles


def _make_use_case(
    provider: FakeLLMProvider,
    default_model: str = "openai/gpt-4o-mini",
    default_system_prompt: str = "Ты — ассистент.",
    users: FakeUserRepository | None = None,
    conversations: FakeConversationRepository | None = None,
    messages: FakeMessageRepository | None = None,
    profiles: FakeProfileRepository | None = None,
) -> tuple[ProcessUserMessage, _Repos]:
    users = users if users is not None else FakeUserRepository()
    conversations = conversations if conversations is not None else FakeConversationRepository()
    messages = messages if messages is not None else FakeMessageRepository()
    profiles = profiles if profiles is not None else FakeProfileRepository()
    factory = _make_repositories_factory(users, conversations, messages, profiles)
    use_case = ProcessUserMessage(
        llm_provider=provider,
        repositories=factory,
        default_model=ModelId(default_model),
        default_system_prompt=default_system_prompt,
        temperature=0.7,
        max_tokens=512,
    )
    return use_case, _Repos(users, conversations, messages, profiles)


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
    async def test_uses_default_model_when_command_has_none(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, default_model="openai/gpt-4o-mini")

        await use_case.execute(_make_command(model_id=None))

        assert provider.received_requests[0].model_id == ModelId("openai/gpt-4o-mini")

    async def test_uses_model_from_command_when_provided(self) -> None:
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, default_model="openai/gpt-4o-mini")

        await use_case.execute(_make_command(model_id=ModelId("anthropic/claude-3-haiku")))

        assert provider.received_requests[0].model_id == ModelId("anthropic/claude-3-haiku")


class TestLLMError:
    """Обязательный сценарий 7: ошибка LLM."""

    async def test_provider_error_propagates(self) -> None:
        error = LLMProviderError(
            message="OpenRouter timeout",
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
    берётся из активного профиля пользователя, а не из статической
    default_system_prompt.
    """

    async def test_system_prompt_equals_active_profile_instruction(self) -> None:
        profile = make_default_profile(name="Экспертный")
        object.__setattr__(profile, "system_instruction", "Отвечай точно и по делу, как эксперт.")
        profiles = FakeProfileRepository([profile])
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(
            provider, default_system_prompt="Фолбэк, не должен использоваться", profiles=profiles
        )

        await use_case.execute(_make_command())

        request = provider.received_requests[0]
        assert request.system_prompt == "Отвечай точно и по делу, как эксперт."

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

        assert provider.received_requests[0].system_prompt == "Кратко и по делу."
        assert provider.received_requests[1].system_prompt == "Отвечай образно, с метафорами."

    async def test_falls_back_to_default_system_prompt_when_profile_instruction_is_blank(self) -> None:
        profile = make_default_profile(name="Пустой")
        object.__setattr__(profile, "system_instruction", "   ")
        profiles = FakeProfileRepository([profile])
        provider = FakeLLMProvider(response=_make_response())
        use_case, _ = _make_use_case(provider, default_system_prompt="Фолбэк-инструкция.", profiles=profiles)

        await use_case.execute(_make_command())

        request = provider.received_requests[0]
        assert request.system_prompt == "Фолбэк-инструкция."
