"""
`require_admin_api_key` — статичная API-key авторизация admin REST
(Sprint 8, задача S8-02, ADR-8.3, скоуп-решение пользователя №1).

Единственная точка сравнения секрета во всём admin-слое: заголовок
`X-Admin-Api-Key` сравнивается с `Settings.admin.api_key` через
`secrets.compare_digest` (защита от timing-атак). И отсутствие, и
неверный ключ → единообразно 401 — единая статичная схема не различает
«аутентифицирован, но не авторизован», различие 401/403 создало бы
ложное впечатление многоуровневой модели прав, которой нет.

Настройки читаются напрямую из `request.app.state.settings` — до задачи
S8-03 (которая публикует `app.state.settings` в `_lifespan` и добавляет
общий accessor `bootstrap.application.get_settings`) это единственный
способ добраться до `Settings` из зависимости; после S8-03 остаётся тем
же самым атрибутом, только уже реально заполненным реальным lifespan'ом
(здесь ничего не меняется).

Каждый admin-роутер обязан подключать эту зависимость на уровне
`APIRouter(dependencies=[Depends(require_admin_api_key)])` — защита «в
глубину», не полагающаяся на то, что её подключит кто-то выше по стеку
(тот же принцип, что и `SelectModel`, не полагающийся только на
Telegram UI, ADR-7.9).

Ключ не логируется ни в каком виде — ни переданное, ни ожидаемое
значение; `shared/logging.py::_SENSITIVE_KEYS` дополнительно перехватил
бы это, если бы кто-то попытался (защитный барьер, не единственная линия
защиты).
"""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from dekoder.shared.config import Settings
from dekoder.shared.logging import get_logger

_logger = get_logger(__name__)

_ADMIN_API_KEY_HEADER = APIKeyHeader(name="X-Admin-Api-Key", auto_error=False)


async def require_admin_api_key(
    request: Request,
    provided_key: str | None = Security(_ADMIN_API_KEY_HEADER),
) -> None:
    """FastAPI-зависимость: поднимает `HTTPException(401)` без верного `X-Admin-Api-Key`, иначе ничего не возвращает."""
    settings: Settings = request.app.state.settings
    expected = settings.admin.api_key.get_secret_value()
    if provided_key is None or not secrets.compare_digest(provided_key, expected):
        _logger.warning("admin_auth_failed", path=request.url.path)
        raise HTTPException(status_code=401, detail="Invalid or missing admin API key")
