"""
`TokenBudgetPolicy` (Sprint 4, задачи S4-02/S4-06, ADR-4.4/4.5) — единая,
детерминированная политика ограничения объёма собранного промпта, с
фиксированным приоритетом сокращения (`backlog_4.md` §3, ADR-4.5).

Тиры сокращения, строго в этом порядке:

    1. секции 1/2 (базовая инструкция, правила безопасности) — неприкосновенны;
    2. последний элемент `messages` (текущий запрос) — неприкосновенен;
    3. секция 3 (профиль) — неприкосновенна;
    4. секция 4 (память) — ограничивается (в Sprint 4 — no-op: `PromptContext.
       confirmed_memory_facts` всегда пуст, `estimate_size("") == 0`, но тир
       реально исполняется — не `# TODO`, ADR-4.5);
    5. секция 5 (RAG/знания) — ограничивается (тот же no-op в Sprint 4);
    6. `messages[:-1]` (вся история, кроме текущего запроса) — обрезается с
       самого старого конца (индекс 0), пока сумма не уложится в бюджет.

Секция 8 (требования к формату ответа) в тирах ADR-4.5 не упомянута ни
как сокращаемая, ни явно как неприкосновенная — по построению она
никогда не совпадает с именем секции 4/5 (единственные сокращаемые тиры),
поэтому фактически ведёт себя как неприкосновенная, наравне с секциями
1/2/3: `backlog_4.md` перечисляет тиры исчерпывающе (только память/RAG/
история — источники, ограничение которых явно предусмотрено 12.6 «Плана
реализации.md»), явных «безлимитных» инструкций/формата ответа среди них нет.

Секции 4/5 сокращаются целиком (весь текст секции убирается), не
частично — на уровне `PromptSection` нет собственной структуры (это уже
склеенный текст, не список отдельных фактов/фрагментов), гранулярное
усечение было бы забеганием вперёд доменных типов Этапа 7/8 (ADR-4.3);
для Sprint 4 это не имеет наблюдаемого эффекта (секции всегда пусты).

Механизм оценки размера (`estimate_size: Callable[[str], int]`,
ADR-4.4) принимается через конструктор — узкий интерфейс, спрятанный от
алгоритма тиров, чтобы замена эвристики на реальный токенизатор в
будущем была изменением одной реализации (`application/prompt/services/
token_budget.py`, задача S4-06), не переписыванием этого файла.

Единственная точка вызова `enforce()` во всём проекте — внутри
`PromptBuilder.build()` (`application/prompt/services/prompt_builder.py`,
задача S4-05, ADR-4.5) — последним шагом сборки, после рендера всех
секций и построения `messages`.

Ноль I/O — чистый алгоритм над уже отрендеренными данными. Обрезание
истории — операция над уже построенным списком `LLMMessage`, не
пересборка промпта заново (ADR-4.5, «Архитектурные заметки»).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from dekoder.application.conversation.dto import LLMMessage
from dekoder.domain.prompt.value_objects import SECTION_KNOWLEDGE, SECTION_MEMORY, PromptSection

SizeEstimator = Callable[[str], int]
"""
Механизм оценки размера текста (ADR-4.4) — эвристика (символы/слова),
не реальный токенизатор; конкретная реализация — `application/prompt/
services/token_budget.py` (задача S4-06).
"""


class TokenBudgetPolicy:
    """
    Реализует ADR-4.5 целиком: тиры 1-6 в фиксированном порядке
    приоритета сокращения, единая точка входа — `enforce()`.
    """

    def __init__(self, estimate_size: SizeEstimator) -> None:
        self._estimate_size = estimate_size

    def enforce(
        self,
        sections: Sequence[PromptSection],
        messages: Sequence[LLMMessage],
        budget: int,
    ) -> tuple[Sequence[PromptSection], Sequence[LLMMessage]]:
        """
        Применяет тиры 1-6 (ADR-4.5) строго по порядку, останавливаясь на
        первом тире, после применения которого суммарный размер укладывается
        в `budget`. Если бюджет уложить невозможно даже после исчерпания
        сокращаемых тиров (4/5/6) — из-за неприкосновенных секций 1/2/3/8
        или единственного (текущего) сообщения — возвращает лучший
        достижимый результат, не поднимая ошибку (ADR-4.5, AC-2: это
        ожидаемо и допустимо).
        """
        if self._total_size(sections, messages) <= budget:
            return sections, messages

        sections = self._reduce_section(sections, SECTION_MEMORY)
        if self._total_size(sections, messages) <= budget:
            return sections, messages

        sections = self._reduce_section(sections, SECTION_KNOWLEDGE)
        if self._total_size(sections, messages) <= budget:
            return sections, messages

        messages = self._trim_oldest_history(sections, messages, budget)
        return sections, messages

    def _total_size(self, sections: Sequence[PromptSection], messages: Sequence[LLMMessage]) -> int:
        sections_size = sum(self._estimate_size(section.text) for section in sections)
        messages_size = sum(self._estimate_size(message.content) for message in messages)
        return sections_size + messages_size

    def _reduce_section(self, sections: Sequence[PromptSection], name: str) -> Sequence[PromptSection]:
        """
        Тир 4/5 (ADR-4.5) — секция с данным `name` полностью очищается
        (весь текст убирается из учёта объёма); остальные секции, включая
        неприкосновенные 1/2/3/8, не затрагиваются. В Sprint 4 это
        детерминированный no-op (`PromptContext.confirmed_memory_facts`/
        `knowledge_fragments` всегда пусты → секция уже пуста), но тир
        реально исполняется на каждом вызове, где бюджет превышен, — не
        закомментированная заглушка (ADR-4.5).
        """
        return [PromptSection(name=section.name, text="") if section.name == name else section for section in sections]

    def _trim_oldest_history(
        self,
        sections: Sequence[PromptSection],
        messages: Sequence[LLMMessage],
        budget: int,
    ) -> Sequence[LLMMessage]:
        """
        Тир 6 (ADR-4.5) — обрезает `messages` с самого старого конца
        (индекс 0), пока суммарный размер не уложится в `budget`, либо
        пока не останется единственное сообщение — последний элемент
        (текущий запрос пользователя) неприкосновенен и не удаляется
        даже при сохраняющемся превышении бюджета.
        """
        if len(messages) <= 1:
            return messages

        trimmed = list(messages)
        sections_size = sum(self._estimate_size(section.text) for section in sections)
        while len(trimmed) > 1:
            messages_size = sum(self._estimate_size(message.content) for message in trimmed)
            if sections_size + messages_size <= budget:
                break
            trimmed.pop(0)
        return trimmed
