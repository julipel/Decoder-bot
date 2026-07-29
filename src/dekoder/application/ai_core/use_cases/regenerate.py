"""
RegenerateUseCase — повторяет операцию с прежними параметрами, либо новый
сценарий, если параметры изменились (docs/versions/01, §9, п.14).
"""

from __future__ import annotations

from dekoder.application.ai_core.commands import RegenerateCommand
from dekoder.application.ai_core.internal_services.session_coordinator import SessionCoordinator
from dekoder.application.ai_core.responses import GenerationResult
from dekoder.application.ai_core.use_cases.generate_content import GenerateContentUseCase


class RegenerateUseCase:
    def __init__(self, session_coordinator: SessionCoordinator, generate_content: GenerateContentUseCase) -> None:
        self._session_coordinator = session_coordinator
        self._generate_content = generate_content

    def execute(self, command: RegenerateCommand) -> GenerationResult:
        raise NotImplementedError
