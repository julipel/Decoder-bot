"""
Use case'ы, стоящие за командами /запомнить, /память, /забыть (docs/01, §3).

Собраны в одном файле: все четыре — тонкие операции над одним и тем же
FactRepositoryPort, а не потому что между ними есть общая логика.
"""

from __future__ import annotations

from dekoder.shared.domain.identifiers import FactDraftId, FactId, UserId
from dekoder.modules.memory.application.ports import FactRepositoryPort
from dekoder.modules.memory.domain.fact import Fact
from dekoder.modules.memory.domain.fact_draft import FactDraft


class StageFactUseCase:
    """Реакция на команду /запомнить <факт> — создаёт черновик, ожидающий подтверждения."""

    def __init__(self, fact_repository: FactRepositoryPort) -> None:
        self._fact_repository = fact_repository

    def execute(self, user_id: UserId, text: str) -> FactDraft:
        raise NotImplementedError


class ConfirmFactUseCase:
    """Подтверждение черновика (кнопка «Сохранить» или явный ответ пользователя)."""

    def __init__(self, fact_repository: FactRepositoryPort) -> None:
        self._fact_repository = fact_repository

    def execute(self, draft_id: FactDraftId) -> Fact:
        raise NotImplementedError


class ListFactsUseCase:
    """Реакция на команду /память."""

    def __init__(self, fact_repository: FactRepositoryPort) -> None:
        self._fact_repository = fact_repository

    def execute(self, user_id: UserId) -> list[Fact]:
        raise NotImplementedError


class ForgetFactUseCase:
    """Реакция на команду /забыть."""

    def __init__(self, fact_repository: FactRepositoryPort) -> None:
        self._fact_repository = fact_repository

    def execute(self, user_id: UserId, fact_id: FactId) -> None:
        raise NotImplementedError
