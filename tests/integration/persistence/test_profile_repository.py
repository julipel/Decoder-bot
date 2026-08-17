"""
Интеграционные тесты `SQLAlchemyProfileRepository` (Sprint 3, задача
S3-05, ADR-3.1) на временной SQLite-базе (`tmp_path` — НЕ рабочая БД).
Стиль fixture'ов — как в `tests/integration/persistence/
test_user_repository.py`: схема создаётся через `Base.metadata.
create_all()` (единственное допустимое исключение для тестового
окружения, backlog_2.md §3); каталог профилей вставляется вручную через
`ProfileORM` (не Alembic bulk_insert — S3-04 — эти тесты проверяют
репозиторий, а не миграцию, которую уже проверяет `test_migrations.py`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.profile.entities import UserProfile
from dekoder.domain.profile.value_objects import ProfileStatus
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.profile_orm import ProfileORM
from dekoder.infrastructure.persistence.profile_repository import SQLAlchemyProfileRepository
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.infrastructure.persistence.user_active_profile_orm import UserActiveProfileORM
from dekoder.infrastructure.persistence.user_orm import UserORM
from dekoder.shared.errors import InfrastructureError


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'profile-repository.db'}"
    test_engine = create_database_engine(database_url)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker:  # type: ignore[type-arg]
    return create_session_factory(engine)


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None)


def _make_profile_orm(
    *, name: str, is_default: bool = False, status: str = "active", is_system: bool = True
) -> ProfileORM:
    now = _now()
    return ProfileORM(
        id=uuid4(),
        name=name,
        description=f"Описание профиля {name}.",
        system_instruction=f"Системная инструкция профиля {name}.",
        response_style="нейтральный",
        target_audience="широкая аудитория",
        formality_level="нейтральный",
        preferred_structure="без требований",
        forbidden_phrasing=[],
        preferred_model=None,
        response_length_hint=None,
        additional_constraints="",
        status=status,
        is_system=is_system,
        is_default=is_default,
        created_at=now,
        updated_at=now,
    )


async def _seed_catalog(
    session_factory: async_sessionmaker,  # type: ignore[type-arg]
    *,
    with_archived: bool = False,
) -> dict[str, UUID]:
    """Вставляет 3 профиля (один — is_default) и, опционально, ещё один архивный. Возвращает id по имени."""
    default_profile = _make_profile_orm(name="Дефолт", is_default=True)
    profile_a = _make_profile_orm(name="Профиль A")
    profile_b = _make_profile_orm(name="Профиль B")
    orm_profiles = [default_profile, profile_a, profile_b]
    if with_archived:
        orm_profiles.append(_make_profile_orm(name="Архивный", status="archived"))

    async with session_factory() as session:
        for orm_profile in orm_profiles:
            session.add(orm_profile)
        await session.commit()

    return {profile.name: profile.id for profile in orm_profiles}


async def _make_user(session_factory: async_sessionmaker, telegram_user_id: int) -> UUID:  # type: ignore[type-arg]
    now = _now()
    async with session_factory() as session:
        user = UserORM(id=uuid4(), telegram_user_id=telegram_user_id, created_at=now, updated_at=now)
        session.add(user)
        await session.commit()
        return user.id


class TestListActive:
    async def test_returns_all_active_profiles(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        ids_by_name = await _seed_catalog(session_factory)

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            profiles = await repository.list_active()

        assert {profile.id for profile in profiles} == set(ids_by_name.values())

    async def test_excludes_archived_profiles(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        ids_by_name = await _seed_catalog(session_factory, with_archived=True)

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            profiles = await repository.list_active()

        returned_names = {profile.name for profile in profiles}
        assert "Архивный" not in returned_names
        assert returned_names == {"Дефолт", "Профиль A", "Профиль B"}
        assert len(profiles) == 3
        assert ids_by_name["Архивный"] not in {profile.id for profile in profiles}


class TestGetActiveProfileDefault:
    """AC-1: без явного выбора возвращается профиль с `is_default=True`."""

    async def test_returns_default_profile_when_user_never_selected(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        ids_by_name = await _seed_catalog(session_factory)
        user_id = await _make_user(session_factory, 111)

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            active_profile = await repository.get_active_profile(user_id)

        assert active_profile.id == ids_by_name["Дефолт"]
        assert active_profile.is_default is True

    async def test_raises_infrastructure_error_when_catalog_is_empty(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        user_id = await _make_user(session_factory, 999)

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            with pytest.raises(InfrastructureError):
                await repository.get_active_profile(user_id)


class TestSelectProfilePersistsChoice:
    """AC-2/AC-3: выбор сохраняется и заменяет предыдущий выбор (upsert, не дублирование строки)."""

    async def test_selected_profile_becomes_active(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        ids_by_name = await _seed_catalog(session_factory)
        user_id = await _make_user(session_factory, 222)

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            selected = await repository.select_profile(user_id, ids_by_name["Профиль A"])
            assert selected is not None
            assert selected.id == ids_by_name["Профиль A"]

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            active_profile = await repository.get_active_profile(user_id)

        assert active_profile.id == ids_by_name["Профиль A"]

    async def test_repeated_selection_replaces_previous_choice_without_duplicating_row(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        ids_by_name = await _seed_catalog(session_factory)
        user_id = await _make_user(session_factory, 333)

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            await repository.select_profile(user_id, ids_by_name["Профиль A"])

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            await repository.select_profile(user_id, ids_by_name["Профиль B"])

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            active_profile = await repository.get_active_profile(user_id)

        assert active_profile.id == ids_by_name["Профиль B"]

        async with session_factory() as session:
            rows = (
                (await session.execute(select(UserActiveProfileORM).where(UserActiveProfileORM.user_id == user_id)))
                .scalars()
                .all()
            )
            assert len(rows) == 1
            assert rows[0].profile_id == ids_by_name["Профиль B"]


class TestSelectProfileRejectsUnknownOrInactive:
    """AC-4: неизвестный/неактивный `profile_id` — `None`, без изменения текущего выбора."""

    async def test_unknown_profile_id_returns_none_and_does_not_change_selection(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        ids_by_name = await _seed_catalog(session_factory)
        user_id = await _make_user(session_factory, 444)

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            await repository.select_profile(user_id, ids_by_name["Профиль A"])

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            result = await repository.select_profile(user_id, uuid4())
            assert result is None

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            active_profile = await repository.get_active_profile(user_id)

        assert active_profile.id == ids_by_name["Профиль A"]

    async def test_archived_profile_id_is_rejected(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        ids_by_name = await _seed_catalog(session_factory, with_archived=True)
        user_id = await _make_user(session_factory, 555)

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            result = await repository.select_profile(user_id, ids_by_name["Архивный"])

        assert result is None


class TestUserIsolation:
    """AC-5: выбор одного пользователя не влияет на другого."""

    async def test_other_user_still_gets_default_profile(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        ids_by_name = await _seed_catalog(session_factory)
        user_a = await _make_user(session_factory, 666)
        user_b = await _make_user(session_factory, 777)

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            await repository.select_profile(user_a, ids_by_name["Профиль A"])

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            active_for_a = await repository.get_active_profile(user_a)
            active_for_b = await repository.get_active_profile(user_b)

        assert active_for_a.id == ids_by_name["Профиль A"]
        assert active_for_b.id == ids_by_name["Дефолт"]


def _make_domain_profile(**overrides: object) -> UserProfile:
    """Sprint 8, S8-06 — доменный `UserProfile` для методов create/update/archive/list_all."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    defaults: dict[str, object] = {
        "id": uuid4(),
        "name": "Новый профиль",
        "description": "Описание",
        "system_instruction": "Инструкция",
        "response_style": "нейтральный",
        "target_audience": "все",
        "formality_level": "нейтральный",
        "preferred_structure": "без требований",
        "forbidden_phrasing": (),
        "preferred_model": None,
        "response_length_hint": None,
        "additional_constraints": "",
        "status": ProfileStatus.ACTIVE,
        "is_system": False,
        "is_default": False,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return UserProfile(**defaults)  # type: ignore[arg-type]


class TestGetById:
    """Sprint 8, S8-06, ADR-8.7."""

    async def test_returns_profile_of_any_status(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        ids_by_name = await _seed_catalog(session_factory, with_archived=True)

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            active = await repository.get_by_id(ids_by_name["Профиль A"])
            archived = await repository.get_by_id(ids_by_name["Архивный"])

        assert active is not None
        assert active.id == ids_by_name["Профиль A"]
        assert archived is not None
        assert archived.status is ProfileStatus.ARCHIVED

    async def test_returns_none_for_unknown_id(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            result = await repository.get_by_id(uuid4())

        assert result is None


class TestCreate:
    """Sprint 8, S8-06, ADR-8.7."""

    async def test_create_then_get_by_id_finds_the_profile(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        new_profile = _make_domain_profile(name="Созданный")

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            await repository.create(new_profile)
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            fetched = await repository.get_by_id(new_profile.id)

        assert fetched is not None
        assert fetched.name == "Созданный"
        assert fetched.is_default is False
        assert fetched.is_system is False

    async def test_two_non_default_profiles_do_not_violate_unique_default_index(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        """`CreateProfile` (S8-07/S8-08) всегда создаёт `is_default=False` — порт должен это допускать."""
        first = _make_domain_profile(name="Первый")
        second = _make_domain_profile(name="Второй")

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            await repository.create(first)
            await repository.create(second)
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            profiles = await repository.list_all()

        assert {profile.id for profile in profiles} == {first.id, second.id}


class TestUpdate:
    """Sprint 8, S8-06, ADR-8.7."""

    async def test_updates_only_editable_fields(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        ids_by_name = await _seed_catalog(session_factory)
        profile_id = ids_by_name["Профиль A"]

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            existing = await repository.get_by_id(profile_id)
        assert existing is not None

        changed = _make_domain_profile(
            id=existing.id,
            name="Профиль A (изменён)",
            preferred_model=ModelId("openai/gpt-4o-mini"),
            status=existing.status,
            is_system=existing.is_system,
            is_default=existing.is_default,
            created_at=existing.created_at,
        )
        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            updated = await repository.update(changed)
            await session.commit()

        assert updated.name == "Профиль A (изменён)"
        assert updated.preferred_model == ModelId("openai/gpt-4o-mini")
        # is_default/is_system/status не входят в изменяемые update() поля инфраструктурного уровня по существу,
        # но use case (S8-07/S8-08) вообще не передаёт их изменёнными — здесь проверяется round-trip через get_by_id.
        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            fetched = await repository.get_by_id(profile_id)
        assert fetched is not None
        assert fetched.is_default is False
        assert fetched.name == "Профиль A (изменён)"

    async def test_raises_infrastructure_error_for_unknown_id(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            with pytest.raises(InfrastructureError):
                await repository.update(_make_domain_profile())


class TestArchive:
    """Sprint 8, S8-06, ADR-8.7."""

    async def test_archives_an_active_profile(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        ids_by_name = await _seed_catalog(session_factory)
        profile_id = ids_by_name["Профиль A"]

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            archived = await repository.archive(profile_id)
            await session.commit()

        assert archived is not None
        assert archived.status is ProfileStatus.ARCHIVED

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            fetched = await repository.get_by_id(profile_id)
        assert fetched is not None
        assert fetched.status is ProfileStatus.ARCHIVED

    async def test_archiving_already_archived_profile_is_idempotent(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        ids_by_name = await _seed_catalog(session_factory, with_archived=True)
        profile_id = ids_by_name["Архивный"]

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            result = await repository.archive(profile_id)  # не должно поднимать исключение
            await session.commit()

        assert result is not None
        assert result.status is ProfileStatus.ARCHIVED

    async def test_returns_none_for_unknown_id(self, session_factory: async_sessionmaker) -> None:  # type: ignore[type-arg]
        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            result = await repository.archive(uuid4())

        assert result is None


class TestListAllIncludesArchived:
    """Sprint 8, S8-06, ADR-8.7 — `list_all()` в отличие от `list_active()` включает архивные профили."""

    async def test_returns_active_and_archived_profiles(
        self,
        session_factory: async_sessionmaker,  # type: ignore[type-arg]
    ) -> None:
        ids_by_name = await _seed_catalog(session_factory, with_archived=True)

        async with session_factory() as session:
            repository = SQLAlchemyProfileRepository(session)
            profiles = await repository.list_all()

        assert {profile.id for profile in profiles} == set(ids_by_name.values())
        statuses = {profile.status for profile in profiles}
        assert ProfileStatus.ACTIVE in statuses
        assert ProfileStatus.ARCHIVED in statuses
