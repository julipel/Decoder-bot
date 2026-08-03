"""
Тесты преобразования Domain↔ORM для `UserProfile` (infrastructure/
persistence/mappers.py, задача S3-03) — round-trip без обращения к базе
данных: UUID, UTC-время, `forbidden_phrasing`, `preferred_model`,
`status`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from dekoder.domain.conversation.value_objects import ModelId
from dekoder.domain.profile.entities import UserProfile
from dekoder.domain.profile.value_objects import ProfileStatus
from dekoder.infrastructure.persistence.mappers import profile_to_domain, profile_to_orm
from dekoder.infrastructure.persistence.profile_orm import ProfileORM


def _now() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _make_profile(**overrides: object) -> UserProfile:
    created_at = _now()
    defaults: dict[str, object] = {
        "id": uuid4(),
        "name": "Экспертный",
        "description": "Точно, структурированно, профессиональная терминология.",
        "system_instruction": "Отвечай точно и структурированно.",
        "response_style": "профессиональный",
        "target_audience": "специалисты",
        "formality_level": "формальный",
        "preferred_structure": "риски и ограничения явно",
        "forbidden_phrasing": (),
        "preferred_model": None,
        "response_length_hint": None,
        "additional_constraints": "",
        "status": ProfileStatus.ACTIVE,
        "is_system": True,
        "is_default": False,
        "created_at": created_at,
        "updated_at": created_at,
    }
    defaults.update(overrides)
    return UserProfile(**defaults)  # type: ignore[arg-type]


class TestProfileMapperRoundTrip:
    def test_round_trip_preserves_data_with_empty_forbidden_phrasing_and_no_preferred_model(self) -> None:
        profile = _make_profile()

        orm_profile = profile_to_orm(profile)

        assert isinstance(orm_profile, ProfileORM)
        assert orm_profile.forbidden_phrasing == []
        assert orm_profile.preferred_model is None
        assert orm_profile.status == "active"
        # Хранимое значение — naive UTC (SQLite не сохраняет offset).
        assert orm_profile.created_at.tzinfo is None
        assert orm_profile.created_at == profile.created_at.replace(tzinfo=None)

        round_tripped = profile_to_domain(orm_profile)

        assert round_tripped == profile
        assert round_tripped.created_at.tzinfo is not None

    def test_round_trip_preserves_non_empty_forbidden_phrasing(self) -> None:
        profile = _make_profile(forbidden_phrasing=("возможно", "наверное", "как бы"))

        orm_profile = profile_to_orm(profile)
        assert orm_profile.forbidden_phrasing == ["возможно", "наверное", "как бы"]

        round_tripped = profile_to_domain(orm_profile)
        assert round_tripped.forbidden_phrasing == ("возможно", "наверное", "как бы")
        assert isinstance(round_tripped.forbidden_phrasing, tuple)

    def test_round_trip_preserves_preferred_model(self) -> None:
        profile = _make_profile(preferred_model=ModelId("openai/gpt-4o-mini"))

        orm_profile = profile_to_orm(profile)
        assert orm_profile.preferred_model == "openai/gpt-4o-mini"

        round_tripped = profile_to_domain(orm_profile)
        assert round_tripped.preferred_model == ModelId("openai/gpt-4o-mini")

    def test_round_trip_preserves_archived_status_and_response_length_hint(self) -> None:
        profile = _make_profile(status=ProfileStatus.ARCHIVED, response_length_hint="короткий")

        orm_profile = profile_to_orm(profile)
        assert orm_profile.status == "archived"
        assert orm_profile.response_length_hint == "короткий"

        round_tripped = profile_to_domain(orm_profile)
        assert round_tripped.status is ProfileStatus.ARCHIVED
        assert round_tripped.response_length_hint == "короткий"

    def test_round_trip_preserves_default_flag_and_updated_at(self) -> None:
        created_at = _now()
        updated_at = created_at + timedelta(hours=1)
        profile = _make_profile(is_default=True, created_at=created_at, updated_at=updated_at)

        round_tripped = profile_to_domain(profile_to_orm(profile))

        assert round_tripped.is_default is True
        assert round_tripped.updated_at == updated_at
