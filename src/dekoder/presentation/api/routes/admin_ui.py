"""
`admin_ui_router` — статичная HTML-страница управления документами базы
знаний (внеспринтовая фича, см. claude.md §32).

Страница не подключает `require_admin_api_key` на уровне роутера —
намеренное исключение из общего правила «всё под `/admin/*` защищено
ключом», тем же приёмом, что публичный `GET /health` рядом с защищённым
`GET /admin/health` (`composition/health.py`): сама разметка не содержит
данных, только статичный HTML/CSS/vanilla JS без сборки и внешних
зависимостей. Ключ администратора пользователь вводит в браузере,
скрипт хранит его в `sessionStorage` вкладки и передаёт заголовком
`X-Admin-Api-Key` при обращении к уже защищённому `admin_documents_router`
(`presentation/api/routes/admin_documents.py`) — сама авторизация не
дублируется и не меняется.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_ADMIN_DOCUMENTS_PAGE = (_STATIC_DIR / "admin_documents.html").read_text(encoding="utf-8")

router = APIRouter(prefix="/admin/ui", tags=["admin-ui"])


@router.get("/documents", response_class=HTMLResponse)
async def get_admin_documents_page() -> HTMLResponse:
    return HTMLResponse(content=_ADMIN_DOCUMENTS_PAGE)
