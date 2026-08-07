"""
`ListAllProfiles` — весь каталог профилей независимо от `status`
(Sprint 8, задача S8-07, ADR-8.7) — в отличие от `ListProfiles`
(`list_active()`, только `ACTIVE`).

Тонкая обёртка над `ConversationRepositoriesFactory` — тот же прецедент,
что и `ListProfiles`.
"""

from __future__ import annotations

from dekoder.application.conversation.ports import ConversationRepositoriesFactory
from dekoder.application.profile.dto import ListAllProfilesResult


class ListAllProfiles:
    def __init__(self, repositories: ConversationRepositoriesFactory) -> None:
        self._repositories = repositories

    async def execute(self) -> ListAllProfilesResult:
        async with self._repositories() as repositories:
            profiles = await repositories.profiles.list_all()
            return ListAllProfilesResult(profiles=tuple(profiles))
