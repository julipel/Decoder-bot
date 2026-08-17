"""
Value objects Prompt Engine (Sprint 4, задача S4-02, ADR-4.1/4.3) —
`PromptSection`, `PromptContext`, `PromptBuildResult`.

`PromptContext.dialogue_history` переиспользует существующий
`domain.conversation.entities.Message` — не вводится параллельный тип
истории (ADR-4.1, прецедент ADR-3.5: `UserProfile.preferred_model`
переиспользует `domain/conversation/value_objects.ModelId` вместо
дублирования). Последний элемент — всегда текущий запрос пользователя
(`MessageRepository.history()` уже возвращает его последней строкой,
ADR-4.1) — это соглашение, не отдельное поле.

`PromptBuildResult.messages` типизирован как `Sequence[application.
conversation.dto.LLMMessage]`, не новым доменным типом — ADR-4.1 требует,
чтобы `ProcessUserMessage.execute()` стал «тривиальным транслятором»
(`LLMRequest(messages=result.messages, ...)` без промежуточного
преобразования); `LLMMessage` сам по себе не имеет зависимостей от
SQLAlchemy/Alembic/Telegram/HTTP (`application/conversation/dto.py` —
обычный `frozen`-датакласс, роль+текст) — единственная причина, по
которой это допустимо здесь, а не полноценная доменно-прикладная
зависимость на use case/порты (`domain/prompt/*` не импортирует ничего
из `application/conversation/ports.py`/репозиториев).

Секции 4/5 (память/RAG) — простые `Sequence[str]`, не новые доменные
типы `MemoryFact`/`KnowledgeFragment` (ADR-4.3, запрещено §21 «Плана
реализации.md» — преждевременное забегание вперёд Этапов 7/8). В
Sprint 4 `PromptContext` всегда передаёт для них пустые коллекции.

Ноль I/O, ноль зависимостей от SQLAlchemy/Alembic/Telegram/HTTP. Ошибки —
обычный `ValueError` (claude.md §20).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from dekoder.application.conversation.dto import LLMMessage
from dekoder.domain.conversation.entities import Message
from dekoder.domain.profile.entities import UserProfile

# Стабильные имена секций 1-5, 8 (ADR-4.3) — совпадают с полем `purpose`
# соответствующего сид-шаблона (`infrastructure/prompts/templates/`,
# задача S4-04) и с `PromptSection.name`, который строит `PromptBuilder`
# (задача S4-05). Общие константы, а не дублированные строковые литералы
# в `policies.py`/`prompt_builder.py` — `TokenBudgetPolicy` (тиры 4/5,
# ADR-4.5) должна опознавать ровно те же секции, которые строит
# `PromptBuilder`.
SECTION_BASE_INSTRUCTION = "base_instruction"
SECTION_SAFETY_RULES = "safety_rules"
SECTION_PROFILE_PARAMETERS = "profile_parameters"
SECTION_MEMORY = "memory_placeholder"
SECTION_KNOWLEDGE = "knowledge_placeholder"
SECTION_RESPONSE_FORMAT = "response_format"

# Порядок секций 1,2,3,4,5,8 в `PromptBuildResult.sections`/итоговом
# `system_prompt` (ADR-4.1/4.3) — секции 6/7 (история диалога, текущий
# запрос) не входят: они образуют `PromptBuildResult.messages`, не
# `sections`.
SECTION_ORDER = (
    SECTION_BASE_INSTRUCTION,
    SECTION_SAFETY_RULES,
    SECTION_PROFILE_PARAMETERS,
    SECTION_MEMORY,
    SECTION_KNOWLEDGE,
    SECTION_RESPONSE_FORMAT,
)


@dataclass(frozen=True, slots=True)
class PromptSection:
    """
    Одна отрендеренная секция промпта (`name` — стабильный идентификатор,
    совпадает с `purpose` шаблона, из которого секция построена; `text` —
    уже подставленный текст).

    `text` может быть пустой строкой — фильтрация пустых секций
    происходит в `PromptBuilder`/`TokenBudgetPolicy`, не здесь (ADR-4.3:
    «исключать пустые секции» — общее правило сборки, не инвариант VO).
    """

    name: str
    text: str


@dataclass(frozen=True, slots=True)
class PromptContext:
    """
    Уже собранный контекст, передаваемый `PromptBuilder.build()` (ADR-4.1/
    4.7/4.8) — `ProcessUserMessage` собирает его из данных, уже полученных
    существующими транзакциями (`profile`, `dialogue_history`); `Prompt
    Builder` никогда не обращается к `ProfileRepository`/
    `ConversationRepositoriesFactory` сам (ADR-4.7).

    `dialogue_history` — последний элемент считается текущим запросом
    пользователя (ADR-4.1): `MessageRepository.history()` уже возвращает
    только что сохранённое сообщение пользователя последней строкой,
    поэтому отдельное поле `current_request: str` не вводится — было бы
    избыточным относительно `dialogue_history[-1]`.

    `confirmed_memory_facts`/`knowledge_fragments` — плейсхолдеры секций
    4/5 (ADR-4.3, Этапы 7/8), в Sprint 4 всегда пустые коллекции.
    """

    profile: UserProfile
    dialogue_history: Sequence[Message]
    confirmed_memory_facts: Sequence[str] = field(default_factory=tuple)
    knowledge_fragments: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.dialogue_history:
            raise ValueError(
                "dialogue_history не может быть пустым — ProcessUserMessage всегда передаёт "
                "хотя бы одно сообщение (только что сохранённый запрос пользователя)"
            )


@dataclass(frozen=True, slots=True)
class PromptBuildResult:
    """
    Результат `PromptBuilder.build()` (ADR-4.1) — готов к тривиальному
    преобразованию в `LLMRequest` вызывающим `ProcessUserMessage`:
    `LLMRequest(system_prompt=result.system_prompt, messages=result.messages, ...)`.

    `system_prompt` — секции 1,2,3,4,5,8, склеенные в фиксированном
    порядке, пустые секции исключены (ADR-4.3). `messages` — секции 6/7
    (история диалога + текущий запрос), role-mapping уже выполнен
    (ADR-4.1). `template_versions` — имя шаблона → версия, для
    метаданных ответа (ADR-4.6). `sections` — неагрегированный список
    секций 1,2,3,4,5,8 (не включает 6/7 — они в `messages`), нужен для
    тестируемости структуры сборки (ADR-4.3) и как вход/выход
    `TokenBudgetPolicy.enforce()` (ADR-4.5).
    """

    system_prompt: str
    messages: Sequence[LLMMessage]
    template_versions: Mapping[str, str]
    sections: Sequence[PromptSection]
