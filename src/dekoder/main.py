"""
ASGI-точка входа процесса (например, uvicorn dekoder.main:app).

Тонкая обёртка над bootstrap-слоем — main.py не содержит конфигурации и
не знает деталей сборки приложения (Modular Monolith, один процесс).

Переключено с `composition.bootstrap.create_app` на
`bootstrap.application.create_application`: первый вертикальный срез
(Telegram → ProcessUserMessage → LLMProvider → внешний агрегатор → ответ)
собирается через новый, более простой bootstrap-слой. `composition/`
не удалён — это отдельное, более крупное дерево заглушек прежней
миграции, которое сейчас этим приложением не используется.
"""

from __future__ import annotations

from dekoder.bootstrap.application import create_application
from dekoder.shared.config import Settings

app = create_application(Settings())
