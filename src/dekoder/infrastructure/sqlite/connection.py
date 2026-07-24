"""
Общая фабрика соединения с SQLite.

Единственный модуль, которому разрешено знать про физический файл базы
данных. *_repository-адаптеры в разных модулях получают соединение через
эту фабрику вместо того, чтобы каждый открывал файл самостоятельно —
SQLite-репозитории не используются напрямую вне своих адаптеров.
Создание таблиц и миграции сюда не входят (вне объёма задачи).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator


class SqliteConnectionFactory:
    """Открывает соединения sqlite3 к общему файлу базы данных приложения."""

    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        raise NotImplementedError
