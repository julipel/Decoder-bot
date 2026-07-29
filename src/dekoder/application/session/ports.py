"""SessionRepository — хранение GenerationSession; не дольше одного незавершённого сценария (docs/versions/05, §7)."""

from __future__ import annotations

from typing import Protocol

from dekoder.domain.session.session import GenerationSession
from dekoder.shared.domain.identifiers import SessionId, UserId


class SessionRepository(Protocol):
    def create(self, user_id: UserId) -> GenerationSession: ...

    def get(self, session_id: SessionId) -> GenerationSession | None: ...

    def get_active_for_user(self, user_id: UserId) -> GenerationSession | None: ...

    def update(self, session: GenerationSession) -> None: ...

    def delete(self, session_id: SessionId) -> None: ...
