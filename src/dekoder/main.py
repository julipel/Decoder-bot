"""
ASGI-точка входа процесса (например, uvicorn dekoder.main:app).

Тонкая обёртка над composition root — main.py не содержит конфигурации
и не знает деталей сборки приложения (docs/02, §1 — единый процесс).
"""

from __future__ import annotations

from dekoder.composition.bootstrap import (
    create_app,  # noqa: F401  (используется после подключения FastAPI)
)

app = None  # заполняется create_app() после подключения FastAPI/Telegram — вне объёма текущей задачи
