"""
`PromptBuilder` и `PromptTemplateRepository` — порты Prompt Engine
(Sprint 4, задача S4-03, ADR-4.1/4.2/4.8).

Только `Protocol`, без реализации — по стилю `application/profile/
ports.py::ProfileRepository`/`application/user/ports.py::UserRepository`/
`application/conversation/ports.py::LLMProvider`: только доменные типы и
типы стандартной библиотеки в сигнатурах, ничего из SQLAlchemy/файловой
системы. Конкретная реализация `PromptTemplateRepository` —
`infrastructure/prompts/file_template_repository.py::FileTemplateRepository`
(задача S4-04); конкретная реализация `PromptBuilder` —
`application/prompt/services/prompt_builder.py::DeterministicPromptBuilder`
(задача S4-05).

`PromptTemplateRepository` не входит в `ConversationRepositories`/
`ConversationRepositoriesFactory` (`application/conversation/ports.py`) —
у Prompt Engine нет отношения к диалоговой транзакции (нет БД, нет
`AsyncSession`, файлы читаются один раз при построении репозитория,
ADR-4.2): вторая, параллельная фабрика репозиториев здесь не вводится
(запрещено `backlog_4.md` §3), `PromptTemplateRepository` внедряется
напрямую через конструктор `application/prompt/services/prompt_builder.py::
DeterministicPromptBuilder`, как и `Settings`/`Clock`/другие
не-БД-зависимые зависимости в проекте.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from dekoder.domain.prompt.entities import PromptTemplate
from dekoder.domain.prompt.value_objects import PromptBuildResult, PromptContext


class PromptBuilder(Protocol):
    """
    Единственная точка формирования системной инструкции и истории
    сообщений, передаваемых `LLMProvider` (ADR-4.1) — ни один Telegram
    handler, use case или LLM-адаптер не строит текст промпта
    самостоятельно.

    `build()` — обычный синхронный метод (`def`, не `async def`):
    реализация не выполняет никакого I/O (ни обращения к БД, ни HTTP, ни
    повторного чтения файлов шаблонов на каждый вызов, ни вызова LLM) —
    чистая функция над уже собранным `PromptContext` (ADR-4.1/4.8). Не
    `Protocol`, требующий `@runtime_checkable` — `ProcessUserMessage`
    получает конкретную реализацию через конструктор (композиция
    `bootstrap/container.py`), структурная проверка в тестах не нужна
    так же остро, как для репозиториев с несколькими fake-реализациями.
    """

    def build(self, context: PromptContext) -> PromptBuildResult: ...


@runtime_checkable
class PromptTemplateRepository(Protocol):
    """
    Абстрактный контракт файлового хранилища шаблонов (ADR-4.2) —
    `@runtime_checkable`, по стилю `ProfileRepository`/`UserRepository`:
    позволяет утверждать структурное соответствие fake-реализаций в
    тестах, не требуя наследования от протокола.

    В отличие от `ConversationRepository.get_by_id`/`ProfileRepository.
    select_profile` (где отсутствие записи — штатный отрицательный
    исход, `None`), отсутствие шаблона с запрошенным именем в Sprint 4
    — ошибка конфигурации, не штатный исход: набор шаблонов фиксирован
    (шесть сид-шаблонов, `backlog_4.md` §5) и не меняется во время
    исполнения. `get()` поднимает исключение (`shared.errors.
    InfrastructureError` в конкретной реализации, не голый `KeyError`),
    называющее отсутствующее имя, а не молча возвращает `None`.
    """

    def get(self, name: str) -> PromptTemplate:
        """Возвращает шаблон по устойчивому идентификатору (`PromptTemplate.id`). Поднимает ошибку, если шаблона нет."""
        ...

    def list_all(self) -> Sequence[PromptTemplate]:
        """Возвращает все загруженные шаблоны — для диагностики/тестов, не рабочий путь `PromptBuilder`."""
        ...
