"""
Сборка приложения: конфигурация → контейнер → HTTP/Telegram driving adapters.

По потоку из docs/02, §9: при старте приложения незавершённые задания
индексации переводятся в состояние, допускающее повторный запуск.
"""

from __future__ import annotations

from dekoder.composition.container import Container


def create_app() -> object:
    """
    Точка сборки процесса:
    1) загружает конфигурацию (config.settings.load_settings);
    2) строит DI-контейнер (composition.container.build_container);
    3) регистрирует HTTP-роуты панели администратора (admin.adapters.http.routes);
    4) подключает Telegram driving adapter (telegram.adapters.bot);
    5) восстанавливает незавершённые задания индексации (recover_interrupted_indexing_jobs).

    Реализация появится вместе с подключением FastAPI и Telegram-библиотеки
    и не входит в объём текущей задачи (создание структуры проекта).
    """
    raise NotImplementedError


def recover_interrupted_indexing_jobs(container: Container) -> None:
    """Переводит документы со статусом «ожидает индексации» дольше ожидаемого в повторно запускаемое состояние."""
    raise NotImplementedError
