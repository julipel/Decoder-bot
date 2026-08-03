"""
Composition Root — DI-контейнер (docs/versions/03, §8).

Единственное место в проекте, которому разрешено импортировать
одновременно application-порты всех модулей и их конкретные адаптеры
(infrastructure/, interfaces/). Контейнер не содержит бизнес-логики —
только создание объектов и внедрение зависимостей через конструкторы.
"""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.application.admin.ports import AdminAuthPort
from dekoder.application.admin.use_cases.archive_knowledge_case import ArchiveKnowledgeCaseUseCase
from dekoder.application.admin.use_cases.authenticate_admin import AuthenticateAdminUseCase
from dekoder.application.admin.use_cases.create_knowledge_case import CreateKnowledgeCaseUseCase
from dekoder.application.admin.use_cases.link_document_to_case import LinkDocumentToCaseUseCase
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
from dekoder.application.ai_core.use_cases.answer_knowledge_question import (
    AnswerKnowledgeQuestionUseCase,
)
from dekoder.application.ai_core.use_cases.generate_content import GenerateContentUseCase
from dekoder.application.ai_core.use_cases.regenerate import RegenerateUseCase
from dekoder.application.ai_core.use_cases.route_command import RouteCommandUseCase
from dekoder.application.knowledge_base.ports import FileStoragePort, KnowledgeRepository
from dekoder.application.knowledge_base.use_cases.get_knowledge_cases import (
    GetKnowledgeCasesUseCase,
)
from dekoder.application.knowledge_base.use_cases.get_knowledge_documents import (
    GetKnowledgeDocumentsUseCase,
)
from dekoder.application.logging.ports import Logger
from dekoder.application.memory.ports import MemoryRepository
from dekoder.application.model_catalog.ports import ModelCatalogRepository
from dekoder.application.model_gateway.ports import ModelGateway
from dekoder.application.prompt_engine.ports import PromptBuilder
from dekoder.application.rag.ports import VectorRepository
from dekoder.application.session.ports import SessionRepository
from dekoder.application.skills.ports import ContentSkillRepository
from dekoder.shared.config import Settings
from dekoder.shared.utils.clock import Clock
from dekoder.shared.utils.correlation import CorrelationIdGenerator


@dataclass
class Container:
    """
    Держит собранные порты (реализованные конкретными адаптерами) и
    use case'ы, готовые к использованию driving-адаптерами
    (interfaces/telegram, interfaces/admin_http).
    """

    # Репозитории и внешние порты
    content_skill_repository: ContentSkillRepository
    model_catalog_repository: ModelCatalogRepository
    session_repository: SessionRepository
    memory_repository: MemoryRepository
    knowledge_repository: KnowledgeRepository
    file_storage: FileStoragePort
    vector_repository: VectorRepository
    model_gateway: ModelGateway
    prompt_builder: PromptBuilder
    logger: Logger
    admin_auth: AdminAuthPort
    clock: Clock
    correlation_id_generator: CorrelationIdGenerator

    # application/ai_core/ — единственный вход для interfaces/telegram
    generate_content: GenerateContentUseCase
    answer_knowledge_question: AnswerKnowledgeQuestionUseCase
    regenerate: RegenerateUseCase
    route_command: RouteCommandUseCase

    # application/admin/ + application/knowledge_base/ — вход для interfaces/admin_http
    authenticate_admin: AuthenticateAdminUseCase
    upload_knowledge_document: UploadKnowledgeDocumentUseCase
    update_knowledge_document: UpdateKnowledgeDocumentUseCase
    remove_knowledge_document: RemoveKnowledgeDocumentUseCase
    create_knowledge_case: CreateKnowledgeCaseUseCase
    update_knowledge_case: UpdateKnowledgeCaseUseCase
    archive_knowledge_case: ArchiveKnowledgeCaseUseCase
    link_document_to_case: LinkDocumentToCaseUseCase
    get_knowledge_documents: GetKnowledgeDocumentsUseCase
    get_knowledge_cases: GetKnowledgeCasesUseCase


def build_container(settings: Settings) -> Container:
    """Собирает все use case'ы, внедряя в них конкретные реализации портов."""
    raise NotImplementedError
