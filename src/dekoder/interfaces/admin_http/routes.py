"""
Admin UI Adapter — HTTP driving adapter панели администратора. Вызывает
только application/admin/ (docs/versions/03, §7). Реальные типы FastAPI —
уже реальная зависимость, как и в composition/health.py.
"""

from __future__ import annotations

from fastapi import APIRouter

from dekoder.application.admin.use_cases.archive_knowledge_case import ArchiveKnowledgeCaseUseCase
from dekoder.application.admin.use_cases.authenticate_admin import AuthenticateAdminUseCase
from dekoder.application.admin.use_cases.create_knowledge_case import CreateKnowledgeCaseUseCase
from dekoder.application.admin.use_cases.link_document_to_case import (
    LinkDocumentToCaseUseCase,
)
from dekoder.application.admin.use_cases.remove_knowledge_document import (
    RemoveKnowledgeDocumentUseCase,
)
from dekoder.application.admin.use_cases.update_knowledge_case import UpdateKnowledgeCaseUseCase
from dekoder.application.admin.use_cases.update_knowledge_document import (
    UpdateKnowledgeDocumentUseCase,
)
from dekoder.application.admin.use_cases.upload_knowledge_document import (
    UploadKnowledgeDocumentUseCase,
)
from dekoder.application.knowledge_base.use_cases.get_knowledge_cases import (
    GetKnowledgeCasesUseCase,
)
from dekoder.application.knowledge_base.use_cases.get_knowledge_documents import (
    GetKnowledgeDocumentsUseCase,
)


def build_admin_router(
    authenticate_admin: AuthenticateAdminUseCase,
    get_knowledge_documents: GetKnowledgeDocumentsUseCase,
    get_knowledge_cases: GetKnowledgeCasesUseCase,
    upload_knowledge_document: UploadKnowledgeDocumentUseCase,
    update_knowledge_document: UpdateKnowledgeDocumentUseCase,
    remove_knowledge_document: RemoveKnowledgeDocumentUseCase,
    create_knowledge_case: CreateKnowledgeCaseUseCase,
    update_knowledge_case: UpdateKnowledgeCaseUseCase,
    archive_knowledge_case: ArchiveKnowledgeCaseUseCase,
    link_document_to_case: LinkDocumentToCaseUseCase,
) -> APIRouter:
    raise NotImplementedError
