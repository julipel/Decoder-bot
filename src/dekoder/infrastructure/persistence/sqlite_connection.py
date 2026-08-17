"""
Общая фабрика соединения с хранилищем структурированных данных (SQLite).

Единственный модуль, которому разрешено знать про физический файл базы
данных. *_repository-адаптеры в persistence/ получают соединение через
эту фабрику вместо того, чтобы каждый открывал файл самостоятельно.
Создание таблиц и миграции сюда не входят (вне объёма задачи).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager


class SqliteConnectionFactory:
    """Открывает соединения sqlite3 к общему файлу базы данных приложения."""

    def __init__(self, database_path: str) -> None:
        self._database_path = database_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        raise NotImplementedError
