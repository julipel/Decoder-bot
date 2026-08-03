"""
In-memory fake-реализации `UserRepository`/`ConversationRepository`/
`MessageRepository`/`ProfileRepository` (`application/user/ports.py`,
`application/conversation/ports.py`, `application/profile/ports.py`) —
общий тестовый helper для всех unit-тестов, использующих
`ProcessUserMessage` (Sprint 2, задача S2-06; `FakeProfileRepository`
добавлен в Sprint 3, задача S3-05 — требуется сразу же, поскольку
`ConversationRepositories` (S3-05, ADR-3.3) получает обязательное поле
`profiles`, без которого существующие вызовы `make_in_memory_
repositories_factory` перестали бы собираться):
`tests/unit/application/test_process_user_message.py`,
`tests/unit/presentation/telegram/test_messages_handler.py`,
`tests/e2e/test_conversation_scenario.py`.

Никакого SQLAlchemy (backlog_2.md §9: «unit-тесты не должны использовать
SQLAlchemy») — только словари в памяти. Реальный persistence-поток
проверяет `tests/integration/test_process_user_message_persistence.py`
и `tests/integration/persistence/test_profile_repository.py` (S3-05).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from dekoder.application.conversation.ports import ConversationRepositories, ConversationRepositoriesFactory
from dekoder.domain.conversation.entities import Conversation, Message
from dekoder.domain.profile.entities import UserProfile
from dekoder.domain.profile.value_objects import ProfileStatus
from dekoder.domain.user.entities import User
from dekoder.shared.errors import InfrastructureError


class FakeUserRepository:
    """In-memory fake порта `UserRepository`."""

    def __init__(self) -> None:
        self._by_telegram_user_id: dict[int, User] = {}

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
        existing = self._by_telegram_user_id.get(telegram_user_id)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        user = User(id=uuid4(), telegram_user_id=telegram_user_id, created_at=now, updated_at=now)
        self._by_telegram_user_id[telegram_user_id] = user
        return user


class FakeConversationRepository:
    """In-memory fake порта `ConversationRepository`."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, Conversation] = {}

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
        existing = await self.get_active_by_user_id(user_id)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        conversation = Conversation(id=uuid4(), user_id=user_id, created_at=now, updated_at=now, closed_at=None)
        self._by_id[conversation.id] = conversation
        return conversation


class FakeMessageRepository:
    """In-memory fake порта `MessageRepository`."""

    def __init__(self) -> None:
        self._by_conversation: dict[UUID, list[Message]] = {}
        self.saved: list[Message] = []

    async def save(self, message: Message) -> Message:
        self._by_conversation.setdefault(message.conversation_id, []).append(message)
        self.saved.append(message)
        return message

    async def history(self, conversation_id: UUID) -> list[Message]:
        return list(self._by_conversation.get(conversation_id, []))

    async def clear(self, conversation_id: UUID) -> int:
        count = len(self._by_conversation.get(conversation_id, []))
        self._by_conversation[conversation_id] = []
        return count


def make_default_profile(*, is_default: bool = True, name: str = "Тестовый") -> UserProfile:
    """
    Профиль по умолчанию для тестов, не проверяющих содержание конкретного
    профиля — только то, что `ConversationRepositories.profiles`
    структурно присутствует и работоспособен (Sprint 3, задача S3-05).
    """
    now = datetime.now(UTC)
    return UserProfile(
        id=uuid4(),
        name=name,
        description="Тестовый профиль по умолчанию.",
        system_instruction="Тестовая системная инструкция.",
        response_style="нейтральный",
        target_audience="тесты",
        formality_level="нейтральный",
        preferred_structure="без требований",
        forbidden_phrasing=(),
        preferred_model=None,
        response_length_hint=None,
        additional_constraints="",
        status=ProfileStatus.ACTIVE,
        is_system=True,
        is_default=is_default,
        created_at=now,
        updated_at=now,
    )


class FakeProfileRepository:
    """
    In-memory fake порта `ProfileRepository` (Sprint 3, задача S3-05).

    По умолчанию содержит один профиль с `is_default=True` — так же, как
    реальный каталог после сид-миграции S3-04 всегда содержит ровно один
    профиль-дефолт; `get_active_profile` на пустом каталоге (при явной
    передаче `profiles=[]`) поднимает `InfrastructureError`, как и
    `SQLAlchemyProfileRepository` (S3-05) — вызывающий код не должен
    молча получать `None`.
    """

    def __init__(self, profiles: list[UserProfile] | None = None) -> None:
        catalog = profiles if profiles is not None else [make_default_profile()]
        self._by_id: dict[UUID, UserProfile] = {profile.id: profile for profile in catalog}
        self._selected: dict[UUID, UUID] = {}

    async def list_active(self) -> list[UserProfile]:
        return [profile for profile in self._by_id.values() if profile.status is ProfileStatus.ACTIVE]

    async def get_active_profile(self, user_id: UUID) -> UserProfile:
        selected_profile_id = self._selected.get(user_id)
        if selected_profile_id is not None:
            return self._by_id[selected_profile_id]
        for profile in self._by_id.values():
            if profile.is_default:
                return profile
        raise InfrastructureError(
            message=f"FakeProfileRepository: не найден профиль с is_default=True для пользователя {user_id}",
            user_message="Не удалось обработать запрос, попробуйте позже.",
            code="PROFILE_ACTIVE_NOT_FOUND",
        )

    async def select_profile(self, user_id: UUID, profile_id: UUID) -> UserProfile | None:
        profile = self._by_id.get(profile_id)
        if profile is None or profile.status is not ProfileStatus.ACTIVE:
            return None
        self._selected[user_id] = profile_id
        return profile


def make_in_memory_repositories_factory(
    users: FakeUserRepository | None = None,
    conversations: FakeConversationRepository | None = None,
    messages: FakeMessageRepository | None = None,
    profiles: FakeProfileRepository | None = None,
) -> ConversationRepositoriesFactory:
    """
    Собирает `ConversationRepositoriesFactory` поверх in-memory fake-реализаций.
    Передавайте одни и те же fake-репозитории между несколькими вызовами
    use case, чтобы смоделировать «продолжение того же диалога».
    """
    users = users if users is not None else FakeUserRepository()
    conversations = conversations if conversations is not None else FakeConversationRepository()
    messages = messages if messages is not None else FakeMessageRepository()
    profiles = profiles if profiles is not None else FakeProfileRepository()

    @asynccontextmanager
    async def _factory() -> AsyncIterator[ConversationRepositories]:
        yield ConversationRepositories(users=users, conversations=conversations, messages=messages, profiles=profiles)

    return _factory
