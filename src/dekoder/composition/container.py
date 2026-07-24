"""
Composition Root — DI-контейнер (модуль 11).

Единственное место в проекте, которому разрешено импортировать
одновременно application-порты всех модулей и их конкретные adapters.
Ни один другой модуль не должен собирать зависимости самостоятельно.
Контейнер не содержит бизнес-логики — только создание объектов и
внедрение зависимостей через конструкторы.
"""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.config.settings import Settings


@dataclass
class Container:
    """
    Держит собранные use case'ы и порты, готовые к использованию driving
    adapters (Telegram, HTTP панели администратора). Поля добавляются по
    мере подключения конкретных адаптеров (SQLite, Qdrant, LLM/Embedding
    провайдеров, Telegram-библиотеки) — вне объёма текущей задачи.
    """


def build_container(settings: Settings) -> Container:
    """Собирает все use case'ы, внедряя в них конкретные реализации портов."""
    raise NotImplementedError
