"""Проверяет, что базовая конфигурация проекта (src-layout, импорт пакета) исправна."""

from __future__ import annotations

import dekoder


def test_package_importable() -> None:
    assert dekoder is not None
