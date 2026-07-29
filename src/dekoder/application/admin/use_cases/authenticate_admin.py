from __future__ import annotations

from dekoder.application.admin.commands import AuthenticateAdminCommand
from dekoder.application.admin.ports import AdminAuthPort


class AuthenticateAdminUseCase:
    def __init__(self, admin_auth: AdminAuthPort) -> None:
        self._admin_auth = admin_auth

    def execute(self, command: AuthenticateAdminCommand) -> str:
        raise NotImplementedError
