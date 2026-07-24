"""
HTTP driving adapter панели администратора (docs/02, §4: «веб-слой —
driving adapter»). FastAPI не подключается на этом шаге (зависимости не
устанавливаются) — только структура маршрутов, вызывающих application
use cases.
"""

from __future__ import annotations

from dekoder.modules.admin.application.use_cases.authenticate_admin import AuthenticateAdminUseCase
from dekoder.modules.admin.application.use_cases.list_knowledge_base import ListCasesUseCase, ListDocumentsUseCase
from dekoder.modules.admin.application.use_cases.manage_cases import (
    ArchiveCaseUseCase,
    CreateCaseUseCase,
    LinkDocumentToCaseUseCase,
    UpdateCaseUseCase,
)
from dekoder.modules.admin.application.use_cases.manage_documents import (
    RemoveDocumentUseCase,
    UpdateDocumentUseCase,
    UploadDocumentUseCase,
)


class AdminRouter:
    """
    Регистрирует HTTP-маршруты панели администратора (аутентификация,
    документы, кейсы) и делегирует их обработку use case'ам. Подключение
    к конкретному веб-фреймворку (FastAPI) — вне объёма текущей задачи.
    """

    def __init__(
        self,
        authenticate_admin: AuthenticateAdminUseCase,
        list_documents: ListDocumentsUseCase,
        list_cases: ListCasesUseCase,
        upload_document: UploadDocumentUseCase,
        update_document: UpdateDocumentUseCase,
        remove_document: RemoveDocumentUseCase,
        create_case: CreateCaseUseCase,
        update_case: UpdateCaseUseCase,
        archive_case: ArchiveCaseUseCase,
        link_document_to_case: LinkDocumentToCaseUseCase,
    ) -> None:
        self._authenticate_admin = authenticate_admin
        self._list_documents = list_documents
        self._list_cases = list_cases
        self._upload_document = upload_document
        self._update_document = update_document
        self._remove_document = remove_document
        self._create_case = create_case
        self._update_case = update_case
        self._archive_case = archive_case
        self._link_document_to_case = link_document_to_case

    def register_routes(self, http_app: object) -> None:
        raise NotImplementedError
