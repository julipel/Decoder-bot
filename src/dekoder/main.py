"""
ASGI-точка входа процесса (например, uvicorn dekoder.main:app).

Тонкая обёртка над composition root — main.py не содержит конфигурации
и не знает деталей сборки приложения (docs/versions/02_system_architecture_v2.0.md,
§3 — Modular Monolith, один процесс).
"""

from __future__ import annotations

from dekoder.composition.bootstrap import create_app
from dekoder.shared.config import Settings

app = create_app(Settings())
