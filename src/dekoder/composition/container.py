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
from dekoder.application.admin.use_cases.authenticate_admin import AuthenticateAdminUseCase
from dekoder.application.ai_core.use_cases.generate_content import GenerateContentUseCase
from dekoder.application.ai_core.use_cases.regenerate import RegenerateUseCase
from dekoder.application.ai_core.use_cases.route_command import RouteCommandUseCase
from dekoder.application.model_catalog.ports import ModelCatalogRepository
from dekoder.application.model_gateway.ports import ModelGateway
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
    (interfaces/telegram).
    """

    # Репозитории и внешние порты
    content_skill_repository: ContentSkillRepository
    model_catalog_repository: ModelCatalogRepository
    session_repository: SessionRepository
    model_gateway: ModelGateway
    admin_auth: AdminAuthPort
    clock: Clock
    correlation_id_generator: CorrelationIdGenerator

    # application/ai_core/ — единственный вход для interfaces/telegram
    generate_content: GenerateContentUseCase
    regenerate: RegenerateUseCase
    route_command: RouteCommandUseCase

    # application/admin/ — вход для будущего admin-интерфейса (Этап 10)
    authenticate_admin: AuthenticateAdminUseCase


def build_container(settings: Settings) -> Container:
    """Собирает все use case'ы, внедряя в них конкретные реализации портов."""
    raise NotImplementedError
