"""Use case входа администратора (docs/02, §13: пароль передаётся по HTTPS и сравнивается с хешем)."""

from __future__ import annotations

from dekoder.modules.admin.application.ports import AdminAuthPort


class AuthenticateAdminUseCase:
    def __init__(self, admin_auth: AdminAuthPort) -> None:
        self._admin_auth = admin_auth

    def execute(self, login: str, password: str) -> str:
        raise NotImplementedError
