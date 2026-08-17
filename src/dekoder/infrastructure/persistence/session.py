"""
Единый механизм управления сессиями SQLAlchemy (Infrastructure Layer).

`async_sessionmaker` создаётся один раз в bootstrap поверх единого
`AsyncEngine` (`create_session_factory()`). `session_scope()` —
единственный способ получить `AsyncSession` за пределами этого модуля:
гарантирует commit при успешном завершении блока, rollback при
исключении и закрытие сессии в обоих случаях.

Сессия не хранится в глобальном изменяемом состоянии и не переиспользуется
несколькими coroutine одновременно — каждый вызов `session_scope()`
создаёт новую независимую `AsyncSession` (требование задачи S2-01).

Задача S2-01 не вводит репозитории и Unit of Work — это только механизм
получения и корректного закрытия сессии, на который будущие репозитории
(следующая задача Sprint 2) будут опираться.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """
    Создаёт единую фабрику сессий поверх переданного `AsyncEngine`.

    `expire_on_commit=False` — объекты, загруженные в сессии, остаются
    доступными для чтения после `commit()` без дополнительного `SELECT`
    (нужно, чтобы вызывающий код мог использовать результат после
    завершения транзакции). `autoflush=False` — момент отправки SQL
    находится под явным контролем вызывающего кода (будущих
    репозиториев), а не срабатывает неявно при каждом запросе.
    """
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def session_scope(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """
    Единая точка получения `AsyncSession` с управляемым жизненным циклом:

    - при успешном завершении блока `async with` — `commit()`;
    - при любом исключении внутри блока — `rollback()`, исключение
      пробрасывается дальше без изменений;
    - сессия закрывается (`close()`) в обоих случаях.

    Не предназначен для совместного использования одной сессии несколькими
    coroutine одновременно — каждый вызов создаёт новую сессию.
    """
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
