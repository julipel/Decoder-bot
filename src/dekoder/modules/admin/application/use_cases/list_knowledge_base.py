"""
Чтение документов/кейсов для отображения в панели администратора.

Тонкие use case'ы нужны, чтобы HTTP-роуты вызывали application use cases,
а не репозитории knowledge_base напрямую.
"""

from __future__ import annotations

from dekoder.modules.knowledge_base.application.ports import CaseRepositoryPort, DocumentRepositoryPort
from dekoder.modules.knowledge_base.domain.case import Case
from dekoder.modules.knowledge_base.domain.document import Document


class ListDocumentsUseCase:
    def __init__(self, document_repository: DocumentRepositoryPort) -> None:
        self._document_repository = document_repository

    def execute(self) -> list[Document]:
        raise NotImplementedError


class ListCasesUseCase:
    def __init__(self, case_repository: CaseRepositoryPort) -> None:
        self._case_repository = case_repository

    def execute(self) -> list[Case]:
        raise NotImplementedError
