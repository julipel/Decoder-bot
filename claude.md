# CLAUDE.md

## 1. Назначение файла

Этот файл содержит обязательный контекст для Claude Code при работе с проектом **«Декодер»**.

Перед анализом, созданием или изменением кода необходимо прочитать этот файл целиком.

Инструкции из этого файла имеют приоритет над предположениями Claude Code о структуре проекта, используемых технологиях и порядке реализации.

При сжатии контекстного окна необходимо сохранять как минимум:

* назначение проекта;
* границы MVP;
* архитектурные принципы;
* направление зависимостей;
* текущий этап разработки;
* запрещённые преждевременные решения;
* правила внесения изменений.

Не следует пытаться реализовать весь проект за одну итерацию. Работа выполняется небольшими проверяемыми шагами.

---

# 2. Краткое описание проекта

**«Декодер»** — персональный AI-ассистент с модульной архитектурой.

Система должна постепенно получить следующие возможности:

* взаимодействие с пользователем через Telegram;
* выбор AI-модели;
* поддержка нескольких авторских профилей и стилей;
* история диалогов;
* долговременная память;
* работа с пользовательской базой знаний;
* RAG-поиск по документам;
* централизованное формирование промптов;
* подключение различных AI-провайдеров;
* дальнейшее подключение голоса, изображений, аналитики и внешних сервисов.

Основная задача разработки — создать расширяемую систему, в которой бизнес-логика не зависит от Telegram, FastAPI, конкретного LLM-провайдера, конкретной базы данных или конкретной AI-модели.

---

# 3. Текущая цель

Текущая цель — реализация MVP поэтапными вертикальными срезами.

Первый обязательный рабочий сценарий:

```text
Пользователь
    ↓
Telegram
    ↓
Telegram Adapter
    ↓
ProcessUserMessage
    ↓
LLMProvider
    ↓
OpenAiCompatibleLLMAdapter (дженерик, LLM_PROVIDER_*)
    ↓
AI-модель
    ↓
Ответ пользователю
```

Сначала должна заработать эта минимальная цепочка.

После неё последовательно добавляются:

1. пользователи;
2. диалоги;
3. сообщения и история;
4. профили;
5. Prompt Engine;
6. долговременная память;
7. база знаний и RAG;
8. выбор моделей;
9. административные функции;
10. логирование, аудит и развёртывание.

Необходимо сохранять работоспособность приложения после каждого этапа.

---

# 4. Границы MVP

В состав MVP входят:

* Telegram-интерфейс;
* текстовые пользовательские запросы;
* AI Core;
* абстракция AI-провайдеров;
* минимум одна рабочая интеграция с LLM;
* выбор модели;
* пользовательские профили;
* история диалога;
* подтверждаемая долговременная память;
* Prompt Engine;
* загрузка текстовых документов;
* RAG через Qdrant;
* SQLite для прикладных данных;
* административные операции;
* журналирование;
* Docker-развёртывание;
* автоматизированные тесты.

В состав текущего MVP не входят, если не поставлена отдельная задача:

* микросервисная архитектура;
* Kubernetes;
* Kafka;
* RabbitMQ;
* Celery;
* Redis;
* PostgreSQL;
* полноценная веб-панель;
* мобильное приложение;
* автоматическое извлечение памяти из всех разговоров;
* графовая база данных;
* Personal Knowledge Graph;
* многоагентная система;
* автономное выполнение действий;
* голосовой интерфейс;
* генерация изображений и видео;
* мониторинг конкурентов;
* аналитический модуль;
* интеграции с календарём, такси, доставкой и умным домом;
* OCR;
* сложная интеллектуальная маршрутизация моделей.

Не добавлять эти компоненты «на будущее» без отдельного требования.

---

# 5. Архитектурный стиль

Проект реализуется как **Modular Monolith**.

Используемые архитектурные подходы:

* Clean Architecture;
* Ports and Adapters;
* Dependency Inversion;
* явное разделение ответственности;
* слабая связанность;
* независимость бизнес-логики от инфраструктуры.

На этапе MVP все функциональные модули находятся в одном репозитории и запускаются как единое приложение или как несколько процессов из одного программного пакета.

Микросервисы не используются.

Модульный монолит не означает размещение всего кода в одном модуле. Каждый функциональный блок должен иметь собственную ответственность и чёткие интерфейсы.

---

# 6. Направление зависимостей

Допустимое направление зависимостей:

```text
presentation
      ↓
application
      ↓
domain
```

Infrastructure реализует интерфейсы, объявленные в application или domain:

```text
infrastructure
      ↓ implements
application ports
```

Bootstrap связывает все компоненты:

```text
bootstrap
 ├── presentation
 ├── application
 ├── infrastructure
 └── configuration
```

## Строго запрещённые зависимости

Нельзя допускать:

```text
domain → FastAPI
domain → Telegram
domain → LLM-провайдер
domain → SQLAlchemy
domain → Qdrant
domain → LangChain

application → Telegram
application → FastAPI
application → LLM-провайдер
application → httpx
application → SQLAlchemy
application → Qdrant

infrastructure → presentation
```

Application может зависеть:

* от domain;
* от собственных DTO;
* от собственных портов;
* от общих прикладных типов и ошибок.

Presentation может зависеть:

* от application;
* от DTO прикладного слоя;
* от Telegram или FastAPI.

Infrastructure может зависеть:

* от внешних библиотек;
* от application ports;
* от domain-типов, если это необходимо для реализации интерфейса.

---

# 7. Основная структура проекта

Целевая структура:

```text
src/
└── dekoder/
    ├── domain/
    │   ├── conversation/
    │   ├── user/
    │   ├── profile/
    │   ├── memory/
    │   ├── prompt/
    │   ├── knowledge/
    │   └── model_catalog/
    │
    ├── application/
    │   ├── conversation/
    │   ├── users/
    │   ├── profile/
    │   ├── memory/
    │   ├── prompt/
    │   ├── knowledge/
    │   └── model_catalog/
    │
    ├── infrastructure/
    │   ├── llm/
    │   ├── database/
    │   ├── qdrant/
    │   ├── documents/
    │   ├── embeddings/
    │   └── prompts/
    │
    ├── presentation/
    │   ├── telegram/
    │   └── api/
    │
    ├── bootstrap/
    │
    └── shared/
```

Не создавать пустую сложную структуру целиком, если соответствующие модули ещё не реализуются.

Новые каталоги добавляются по мере появления реальной функциональности.

**Текущее фактическое состояние (после Sprint 8, LLM-часть Sprint 11):**
реально используется полное дерево согласно этой целевой структуре —
`domain/{conversation,user,profile,memory,prompt,knowledge,model_catalog}`,
`application/{conversation,user,profile,memory,prompt,knowledge,model_catalog,health}`,
`infrastructure/{llm,persistence,qdrant,documents,embeddings,prompts,model_catalog,health}`,
`presentation/{telegram,api}`, `bootstrap/`, `shared/`. Подробности по
слоям — см. §32/§36.

Отдельно, **параллельно и не используется реально запускаемым
приложением**, в репозитории по-прежнему существует более крупное
дерево-заглушка (`composition/`, `interfaces/`, а также остатки
`domain/`/`application/`-модулей `ai_core`, `admin`, `rag`, `session`,
`skills`, `knowledge_base`, `infrastructure/model_gateway`,
`infrastructure/vector_storage`, `shared/domain/identifiers.py`) —
результат отдельной, более ранней и гораздо более крупной миграции по
документам `docs/versions/*_v2.0.md`, выполненной **до** прочтения этого
файла, по своей собственной, отличной от Sprint 1+ архитектуре
(`interfaces/`+`composition/` вместо `presentation/`+`bootstrap/`).
Каждый спринт по мере построения настоящего аналога точечно удаляет
пересекающийся узел этого дерева (см. §36 «Известные расхождения») —
полная реконсиляция остального по-прежнему осознанно отложена, не
предпринимать её без явного запроса.

---

# 8. Ответственность слоёв

## 8.1 Domain

Domain содержит:

* сущности;
* value objects;
* enum;
* доменные правила;
* политики;
* доменные ошибки;
* инварианты.

Domain не должен знать:

* откуда пришёл запрос;
* где хранятся данные;
* какой AI-провайдер используется;
* какой web framework используется;
* какой формат имеет внешний API.

Примеры доменных объектов:

* `MessageText`;
* `Conversation`;
* `MemoryRecord`;
* `UserProfile`;
* `KnowledgeDocument`;
* `AIModel`.

---

## 8.2 Application

Application содержит:

* use cases;
* команды;
* DTO;
* порты;
* координацию доменных объектов;
* прикладные политики;
* транзакционные сценарии.

Примеры:

* `ProcessUserMessage`;
* `StartConversation`;
* `SelectProfile`;
* `FindRelevantMemory`;
* `SearchKnowledge`;
* `SelectModel`.

Application определяет, **что** должна выполнить система, но не знает, **как технически** вызывается Telegram, настроенный LLM-провайдер, SQLite или Qdrant.

---

## 8.3 Infrastructure

Infrastructure содержит реализации портов:

* OpenAiCompatibleLLMAdapter (дженерик OpenAI-Chat-Completions-совместимый, ADR-11.1);
* другие LLM-адаптеры;
* SQLAlchemy repositories;
* Qdrant repository;
* парсеры PDF, DOCX и TXT;
* embedding adapters;
* файловое хранилище;
* внешние HTTP-клиенты.

Infrastructure не должна содержать бизнес-решения.

Например, `OpenAiCompatibleLLMAdapter` не решает:

* какой профиль выбрать;
* какую память включить;
* нужно ли выполнять RAG;
* какой системный промпт использовать.

Он только преобразует внутренний запрос во внешний формат и внешний ответ во внутренний результат.

---

## 8.4 Presentation

Presentation содержит:

* Telegram handlers;
* FastAPI routes;
* request и response schemas;
* преобразование внешнего ввода во внутренние команды;
* преобразование прикладного результата в ответ пользователю.

Handlers и routes должны быть тонкими.

Они не должны:

* обращаться напрямую к базе данных;
* создавать AI-адаптер;
* собирать бизнес-промпт;
* выбирать профиль;
* выполнять RAG;
* реализовывать бизнес-правила.

---

## 8.5 Bootstrap

Bootstrap является единственным местом композиции приложения.

Он создаёт:

* Settings;
* HTTP-клиенты;
* репозитории;
* инфраструктурные адаптеры;
* use cases;
* Telegram handlers;
* FastAPI application.

Не использовать глобальный service locator.

Не создавать зависимости внутри handlers и use cases.

**Уточнение объёма понятия «bootstrap».** «Bootstrap» здесь — это роль
(единственная точка сборки), а не только каталог `bootstrap/`. Тонкие
entry-point файлы процесса (`main.py`, `telegram_main.py` — каждый
только создаёт `Settings()` и сразу передаёт её в `bootstrap/`, не
принимая других решений) считаются частью composition root наравне с
пакетом `bootstrap/`. Требование нарушается, если создание `Settings`
или сборка зависимостей появляется где-то ещё — в handlers, use cases,
адаптерах или при импорте произвольного модуля, — а не из-за того, что
`Settings()` физически вызван на уровне entry-point файла, а не внутри
`bootstrap/*.py`. Пример допустимого разделения — `main.py` вызывает
`bootstrap.application.create_application(Settings())`
(`create_application` продолжает принимать `Settings` параметром,
что и делает конфигурацию тестируемой без переменных окружения
процесса, см. §18).

---

# 9. Технологический стек

Основной стек:

* Python 3.11;
* FastAPI;
* Pydantic;
* pydantic-settings;
* python-telegram-bot;
* httpx;
* SQLAlchemy;
* Alembic;
* SQLite;
* Qdrant;
* Docker;
* Docker Compose;
* pytest;
* pytest-asyncio;
* respx;
* Ruff;
* MyPy;
* structlog.

LangChain не является архитектурным ядром проекта.

Допускается использовать LangChain только внутри infrastructure, если он действительно упрощает:

* загрузку документов;
* разбиение текста;
* интеграцию с конкретным embedding provider.

Domain и application не должны зависеть от типов LangChain.

---

# 10. Работа с AI-моделями

Прикладной слой использует абстрактный порт:

```python
class LLMProvider(Protocol):
    async def generate(self, request: LLMRequest) -> LLMResponse:
        ...
```

Внутренние структуры:

```text
LLMRequest
LLMResponse
ModelId
ProviderId
GenerationSettings
```

Application не должен принимать или возвращать:

* JSON-формат Chat Completions конкретного LLM-провайдера;
* OpenAI SDK objects;
* LangChain messages;
* `httpx.Response`;
* Telegram Update.

Первая реализация:

```text
OpenAiCompatibleLLMAdapter
```

В дальнейшем могут быть добавлены:

* OpenAI Adapter;
* YandexGPT Adapter;
* Claude Adapter;
* Gemini Adapter;
* Ollama Adapter.

Добавление нового адаптера не должно требовать изменения основного use case обработки сообщения.

---

# 11. Основной прикладной сценарий

Главный use case:

```text
ProcessUserMessage
```

Он координирует (реализовано полностью, Sprint 1–7):

1. идентификацию пользователя;
2. получение активного диалога;
3. сохранение пользовательского сообщения;
4. получение активного профиля;
5. получение релевантной памяти;
6. выполнение RAG-поиска;
7. получение истории;
8. передачу данных в Prompt Engine;
9. выбор модели;
10. вызов `LLMProvider`;
11. сохранение ответа;
12. возврат результата интерфейсу.

Не следует превращать `ProcessUserMessage` в огромный класс. Логика делегирована отдельным use cases и application services по мере роста сценария:

* `BuildConversationContext`;
* `FindRelevantMemory`;
* `SearchKnowledge`;
* `BuildPrompt`;
* `ResolveSelectedModel`.

---

# 12. Prompt Engine

Prompt Engine является централизованным компонентом формирования запроса к AI (реализован, Sprint 4).

Он собирает:

```text
Базовая системная инструкция
+
Правила безопасности
+
Активный профиль
+
Подтверждённая память
+
RAG-контекст
+
История диалога
+
Текущий запрос
+
Требования к формату ответа
```

Prompt Engine:

* не вызывает AI-модель;
* не обращается напрямую к Telegram;
* не выполняет поиск в Qdrant;
* не сохраняет данные;
* не читает `.env`.

Он получает подготовленные данные и возвращает структурированный `PromptBuildResult`.

Промпты не должны формироваться:

* в Telegram handlers;
* в `OpenAiCompatibleLLMAdapter`;
* в FastAPI routes;
* в случайных участках use cases.

---

# 13. Диалоги и история

Основные сущности (реализовано, Sprint 2): `User`, `Conversation`, `Message`, `MessageRole`.

Правила:

* диалог принадлежит одному пользователю;
* сообщение принадлежит одному диалогу;
* история пользователей изолирована;
* завершённый диалог не изменяется;
* контекст модели ограничивается отдельной политикой;
* история диалога не является долговременной памятью.

Не передавать модели всю историю без ограничений. Ограничение контекста — `TokenBudgetPolicy` (Sprint 4, `domain/prompt/policies.py`).

---

# 14. Пользовательские профили

Профиль определяет: стиль, тон, целевую аудиторию, правила ответа, структуру, ограничения, при необходимости предпочтительную модель.

Правила:

* пользователь может иметь несколько профилей;
* один профиль активен;
* профиль по умолчанию всегда доступен;
* профиль изменяется только явно;
* новые настройки не извлекаются автоматически из разговора;
* профиль влияет только на последующие ответы.

Профиль не должен храниться в Telegram handler или глобальной переменной.

Реализовано полностью (Sprint 3): каталог общий (не персональный, ADR-3.1), выбор через `/profile`. Admin CRUD каталога (create/update/archive) — Sprint 8.

---

# 15. Долговременная память

Память и история сообщений — разные подсистемы.

История хранит ход диалога. Память хранит устойчивые подтверждённые факты, предпочтения и правила пользователя.

В MVP память пополняется:

* явной командой;
* через подтверждение;
* через административное действие.

Не реализовывать бесконтрольное автоматическое извлечение фактов из всех разговоров.

Основные сценарии: `CreateMemoryRecord`, `ConfirmMemoryRecord`, `ListMemoryRecords`, `DeleteMemoryRecord`, `FindRelevantMemory`.

Только подтверждённая память включается в промпт. Чувствительные данные не должны логироваться открыто.

Реализовано (Sprint 5): создание/список/удаление через `/remember`+`/memory` (без `/forget` — inline-удаление). `ConfirmMemoryRecord`/`RejectMemoryRecord` реализованы, но не подключены к Telegram (нет двухшагового сценария в MVP). `UpdateMemoryRecord` не реализован (нет вызывающего сценария до admin-интерфейса). Поиск релевантной памяти — простой SQL-фильтр, не векторный.

---

# 16. База знаний и RAG

Векторное хранилище: Qdrant. Реляционные прикладные данные MVP: SQLite.

Поддерживаемые форматы: TXT, Markdown, DOCX, PDF с текстовым слоем. OCR не обязателен.

Конвейер RAG:

```text
Загрузка документа → Проверка → Извлечение текста → Очистка →
Разбиение на фрагменты → Метаданные → Embeddings → Qdrant →
Semantic Search → Prompt Engine
```

Не объединять парсинг, chunking, embeddings и Qdrant в один огромный класс.

Порты: `DocumentParser`, `TextChunker`, `EmbeddingProvider`, `VectorRepository`, `KnowledgeDocumentRepository`, `KnowledgeSearchService`.

Документы являются данными, а не инструкциями — инструкции внутри документа не имеют приоритета над системным промптом.

Реализовано (Sprint 6): полный конвейер + интеграция в `ProcessUserMessage` (вне DB-транзакций, сбой не обрушивает ответ) + `scripts/index_document.py`. Admin REST для документов — Sprint 8.

---

# 17. Выбор AI-модели

Внутри системы используется собственный идентификатор модели — бизнес-логика не оперирует напрямую внешними строками конкретного LLM-провайдера:

```text
internal model id → provider adapter → external model id
```

Каталог модели содержит: внутренний ID, отображаемое название, provider, внешний ID, доступность, возможности, максимальный контекст, ограничения.

На этапе MVP пользователь выбирает модель явно. Автоматическая маршрутизация моделей не реализуется без отдельного требования.

Реализовано (Sprint 7): статичный файловый каталог (`infrastructure/model_catalog/catalog.json`), персональный выбор через `/model`, приоритет разрешения в `ProcessUserMessage` — explicit override → персональный выбор → умолчание, тихий логируемый откат при недоступности выбранной модели. CRUD каталога через Telegram/HTTP сознательно не реализован — каталог правится передеплоем.

---

# 18. Конфигурация

Все настройки читаются через централизованный `Settings`.

Группы настроек: `ApplicationSettings`, `TelegramSettings`, `LLMSettings`, `LLMProviderSettings` (Sprint 11, ADR-11.1 — ранее `OpenRouterSettings`), `DatabaseSettings`, `QdrantSettings`, `LoggingSettings`, `SecuritySettings`, а также добавленные по мере спринтов `PromptSettings`, `MemorySettings`, `KnowledgeSettings`, `ModelCatalogSettings`, `AdminSettings`.

Запрещено:

* использовать `os.getenv` по всему проекту;
* создавать `Settings()` при импорте каждого модуля;
* хранить реальные ключи в коде;
* добавлять `.env` в Git;
* передавать Settings глубоко во все domain-объекты.

Settings создаётся в bootstrap (в этой роли — включая тонкие entry-point файлы `main.py`/`telegram_main.py`, см. уточнение в §8.5) и преобразуется в конкретные параметры зависимостей.

Секреты должны использовать `SecretStr` или эквивалент.

---

# 19. Работа с HTTP-клиентами

Использовать `httpx.AsyncClient`.

Клиент: создаётся централизованно, передаётся адаптеру, переиспользуется, закрывается через lifecycle, не создаётся заново на каждый AI-запрос.

Обязательна обработка: timeout, network error, 401, 403, 429, 5xx, некорректный JSON, отсутствующий результат.

Не выполнять автоматический retry без явной политики — повторный запрос к AI может привести к дополнительной оплате и задержке.

---

# 20. Ошибки

Иерархия (реализована в `src/dekoder/shared/errors.py`):

```text
DekoderError
├── ValidationError
├── ApplicationError
├── NotFoundError (добавлен Sprint 8)
└── InfrastructureError
    └── ExternalServiceError
        └── LLMProviderError
```

`DomainError`/`AccessDeniedError`/`ConfigurationError`/`KnowledgeSearchError` из первоначального плана по-прежнему не созданы — ни один сценарий их ещё не требует (§29/§31: не создавать классы заранее). Добавлять нужно вместе с первым реальным сценарием, который их использует, не раньше (Этап 11).

Ошибка должна содержать: внутренний код, техническое сообщение, безопасное пользовательское сообщение, необязательную причину, необязательные метаданные.

Пользователь не должен видеть: stack trace, API key, URL с секретами, внутренний JSON провайдера, системный промпт, внутренние пути файлов.

Infrastructure errors должны преобразовываться в прикладные ошибки до presentation-слоя. FastAPI-слой имеет глобальные `exception_handler`'ы (Sprint 8, `presentation/api/error_handlers.py`).

---

# 21. Логирование

Используется структурированное логирование (structlog, JSON в stdout).

Рекомендуемые поля: timestamp, level, event, correlation_id, user_id (обезличенный), conversation_id, provider, model, duration_ms, status, error_code.

Не логировать: API keys, Telegram token, Authorization header, полный текст пользовательского сообщения, полный ответ AI, полное содержимое памяти, чувствительные данные профиля.

Каждый пользовательский запрос должен получать `correlation_id`. Полноценный просмотр/агрегация логов и метрик, сквозной `correlation_id` через весь стек — Этап 11, не реализовано.

---

# 22. Telegram-интерфейс

Telegram является presentation adapter.

Handler: получает Update → извлекает данные → создаёт application command → вызывает use case → преобразует результат в ответ → обрабатывает ошибки.

Handler не должен: вызывать LLM-провайдера напрямую, читать `.env`, обращаться к SQLAlchemy/Qdrant, создавать промпты, принимать бизнес-решения.

Длинные сообщения делятся на части с учётом лимита Telegram. Не использовать глобальное изменяемое состояние для пользовательского контекста.

---

# 23. FastAPI

FastAPI используется для: health endpoints, административных endpoints, возможных webhooks, будущих интеграций.

Routes должны быть тонкими — не содержать SQL-запросы, не вызывать Qdrant напрямую, не создавать adapters, не содержать бизнес-правила.

Фабрика приложения: `create_application`. Ресурсы управляются через lifespan.

Реализовано (Sprint 8): `/health` (публичный, дешёвый), `/admin/health` (реальный health-check Qdrant/OpenRouter/OpenAI, всегда 200), `/admin/documents/*`, `/admin/profiles/*` — все под статичной API-key авторизацией (`X-Admin-Api-Key`/`ADMIN_API_KEY`, `require_admin_api_key`).

---

# 24. База данных

На этапе MVP используется SQLite. SQLAlchemy 2.x (async) + Alembic — подключены (Sprint 2).

Repository interfaces объявляются в application, SQLAlchemy implementations — в infrastructure. ORM-модели не передаются в presentation. Прикладной слой не принимает `AsyncSession`.

---

# 25. Docker

Один программный пакет запускается как несколько процессов: API, Telegram polling. Два контейнера из одного образа (`api`, `telegram-bot`) — не делает систему микросервисной.

Не добавлять без необходимости: PostgreSQL, Redis, очереди, workers.

Docker image: не содержит `.env`, запускается не от root, Python 3.11 slim, корректно завершает процессы, healthcheck для API.

---

# 26. Тестирование

Каждая новая функция сопровождается тестами.

**Unit tests** — domain, policies, use cases, Prompt Engine, преобразование ошибок, бизнес-правила; не вызывают реальные API.

**Integration tests** — HTTP adapters через mock server (`respx`), repositories, SQLite, Qdrant, parsers, Telegram handlers, FastAPI routes.

**Acceptance/e2e tests** — основные пользовательские сценарии; не сравнивать полный текст недетерминированного ответа реальной модели, проверять факт вызова, сформированный запрос, структуру ответа, ошибки, метаданные.

---

# 27. Инструменты качества

Перед завершением задачи должны проходить:

```bash
ruff format --check .
ruff check .
mypy src
pytest
```

При необходимости: `pytest --cov=dekoder --cov-report=term-missing`.

Не отключать проверки глобально ради исправления одной ошибки. Не использовать массово `# type: ignore` — каждое исключение должно быть обосновано.

---

# 28. Правила именования

Предпочтительны имена, выражающие бизнес-смысл (`ProcessUserMessage`, `BuildConversationContext`, `FindRelevantMemory`, `SelectProfile`, `SearchKnowledge`, `OpenAiCompatibleLLMAdapter`, `ConversationRepository`).

Избегать безликих имён (`Manager`, `Helper`, `Utils`, `Processor`, `Common`, `BaseService`, `DataHandler`), если ответственность из имени неясна.

Один класс — одна основная ответственность.

---

# 29. Правила работы Claude Code

Перед внесением изменений Claude Code должен:

1. прочитать этот файл;
2. определить текущий этап;
3. изучить существующую структуру;
4. проверить уже реализованные интерфейсы;
5. не дублировать существующий код;
6. перечислить предполагаемые изменения;
7. внести минимально достаточное изменение;
8. запустить проверки;
9. сообщить о найденных расхождениях.

При получении задачи Claude Code не должен автоматически: переписывать всю архитектуру, переименовывать множество файлов, менять публичные интерфейсы без необходимости, подключать новые библиотеки, добавлять будущие модули, создавать сложные абстракции, исправлять несвязанные участки кода, удалять архитектурные документы.

---

# 30. Формат выполнения задач

**Шаг 1. Анализ** — какие файлы уже существуют, какие компоненты затрагиваются, какие архитектурные ограничения применимы, есть ли противоречия.

**Шаг 2. План изменений** — создаваемые/изменяемые файлы, тесты, возможные миграции, зависимости.

**Шаг 3. Реализация** — только изменения, необходимые для текущей задачи.

**Шаг 4. Проверка** — `ruff format --check .`, `ruff check .`, `mypy src`, `pytest`.

**Шаг 5. Отчёт** — что реализовано, какие файлы изменены, какие проверки пройдены, какие ограничения остались, есть ли технический долг.

---

# 31. Запрет на скрытое изменение архитектуры

Если текущая задача требует отступления от архитектуры, Claude Code должен: не вносить изменение молча; объяснить противоречие; предложить минимальный вариант; дождаться отдельного решения, если изменение существенное.

Существенными считаются: смена архитектурного стиля, добавление микросервиса, замена базы данных, изменение направления зависимостей, удаление порта, перенос бизнес-логики в infrastructure, добавление нового AI-фреймворка, изменение публичных контрактов нескольких модулей.

---

# 32. Текущий этап разработки

**Sprint 11 (производственное развёртывание + генерализация LLM-провайдера) — LLM-часть выполнена (S11-01/S11-02), остальное не начато.** Начиная с этого спринта — `LLMProviderSettings`/`OpenAiCompatibleLLMAdapter`/`OpenAiCompatibleHealthCheck` (ранее `OpenRouterSettings`/`OpenRouterLLMAdapter`); LLM-адаптер стал дженерик OpenAI-Chat-Completions-совместимым, настраиваемым только через `.env` (`LLM_PROVIDER_*`) — причина: OpenRouter географически недоступен пользователю. `catalog.json` id моделей остаются иллюстративным дефолтом в конвенции OpenRouter (`vendor/model-name`) — требуют ручной правки при смене `LLM_PROVIDER_BASE_URL` на другой реальный агрегатор.

Полная архитектурная спецификация каждого спринта — внешние `backlog_N.md` (не входят в этот репозиторий, содержат ADR). Итог по завершённым спринтам (все — полный вертикальный срез, ruff/mypy/pytest зелёные на каждом коммите; подробности по файлам/тестам/девиациям — `git log`/сообщения коммитов):

* **Sprint 1 — Walking Skeleton (завершён).** Telegram → `ProcessUserMessage` → `LLMProvider` → OpenRouter-адаптер → ответ. Settings, structlog-логирование, 5-классовая иерархия ошибок, `/start` + текстовый хендлер, Docker, 143 теста.
* **Sprint 2 — постоянное хранилище, диалоги, история (S2-01…S2-11, завершён).** SQLAlchemy async + Alembic; `User`/`Conversation`/`Message` (domain+ORM+mapper+миграция); `UserRepository`/`ConversationRepository`/`MessageRepository`; `ProcessUserMessage` расширен историей (3 короткие транзакции — сохранить user message / прочитать историю / сохранить assistant message; вызов LLM строго вне транзакций); `StartNewConversation`+`/new`; `ClearConversation`+`/clear`. Финальный аудит нашёл и исправил 3 реальных дефекта: недетерминированный тай-брейк сортировки сообщений при совпадающем `created_at` (Windows возвращает одинаковый `datetime.now(UTC)` при быстрых последовательных вызовах — исправлено гарантией строго возрастающего `created_at` внутри `ProcessUserMessage`), `Dockerfile` не давал непривилегированному пользователю создать `/app/data`, `docker-compose.yml` не монтировал `/app/data` в volume (SQLite терялась при пересборке). 354 теста.
* **Sprint 3 — пользовательские профили (S3-01…S3-09, завершён).** `UserProfile`/`ProfileStatus` (domain); `ProfileORM` + миграция + сид-миграция (4 профиля-каталога, один `is_default`); `ProfileRepository` (`get_active_profile` — один SQL-запрос с `COALESCE` на дефолт, `select_profile` — атомарный upsert); `ListProfiles`/`GetActiveProfile`/`SelectProfile`; интеграция в `ProcessUserMessage` (`system_prompt` из активного профиля); `/profile` с inline-клавиатурой. Финальный аудит исправил один дефект: `Dockerfile` не копировал `alembic.ini`/`alembic/` в образ. 427 тестов. *Follow-up после Sprint 11:* отдельная data-миграция заменила текст тех же 4 сид-профилей на авторские персоны («Честный друг», «Психолог-наставник», «Личный ассистент» — default, «Контент-стратег») — `id`/`is_default`-слот не изменились.
* **Sprint 4 — Prompt Engine (S4-01…S4-08, завершён).** `domain/prompt` (`PromptTemplate`, `PromptContext`, `PromptBuildResult`, `TokenBudgetPolicy` — 6 тиров сокращения по приоритету); `PromptBuilder`/`PromptTemplateRepository` порты; `FileTemplateRepository` + 6 сид-шаблонов (JSON-манифест, `string.Template`; понадобился `package-data` в `pyproject.toml`, иначе `pip install .` не включал бы шаблоны в wheel — обнаружено сборкой образа); `DeterministicPromptBuilder` (единственная реализация); эвристика бюджета по символам (не токенизатор) + `PromptSettings.token_budget`; интеграция в `ProcessUserMessage` (`_DEFAULT_SYSTEM_PROMPT` удалён — база текста теперь всегда отрендерена как секция 1 шаблона). Финальный аудит не нашёл новых дефектов. 496 тестов.
* **Sprint 5 — долговременная память (S5-01…S5-08, завершён).** `domain/memory` (`MemoryRecord`, `MemoryCategory`/`Source`/`Status`/`Confidence`); `MemoryRepository` + миграция (без сида); `Create`/`Confirm`/`Reject`/`List`/`DeleteMemoryRecord` (`Confirm`/`Reject` реализованы, но не подключены к Telegram — нет двухшагового сценария в MVP); интеграция в `ProcessUserMessage` (`find_relevant` читается в транзакции 1, факты идут в `PromptContext`, Prompt Engine не тронут); `/remember`+`/memory` (inline-удаление, без `/forget`); чувствительные записи (`is_sensitive`) никогда не логируются текстом. Финальный аудит не нашёл новых дефектов. 565 тестов.
* **Sprint 6 — база знаний и RAG (S6-01…S6-11, завершён; не задокументирован отдельной записью в момент выполнения — восстановлено по коммитам).** `domain/knowledge`, `application/knowledge`, `infrastructure/{documents,embeddings,qdrant}`; парсеры (txt/md/docx/pdf), chunking, `OpenAiEmbeddingProvider`, `SemanticSearchService`; интеграция в `ProcessUserMessage` (`_search_knowledge`, вне DB-транзакций, сбой не обрушивает ответ); `scripts/index_document.py`.
* **Sprint 7 — выбор AI-модели (S7-01…S7-08, завершён).** `domain/model_catalog` (`AIModel`, `AIProvider`/`ModelCapability`/`ModelAvailability`/`ModelPriceTier`, `GenerationSettings`); `ConfigModelCatalogRepository` (`catalog.json`, 6 моделей — тоже потребовал `package-data`-фикса); `ModelSelection`+`ModelSelectionRepository` (upsert на пользователя); `ListAvailableModels`/`GetSelectedModel`/`SelectModel` (`SelectModel` — доменная ошибка на невалидный/недоступный выбор, не молчаливый no-op); интеграция в `ProcessUserMessage` (приоритет: explicit override → персональный выбор → default; тихий логируемый откат при недоступности); `/model` с inline-клавиатурой. Финальный аудит не нашёл новых дефектов кода (только точечная правка докстринга). 741 тест.
* **Sprint 8 — административные функции (S8-01…S8-11, завершён).** `AdminSettings` (статичный `X-Admin-Api-Key`); глобальные FastAPI `exception_handler`'ы; `NotFoundError` (новый класс ошибок); admin REST для документов (upload/list/get/delete/reindex) и профилей (create/patch/archive/list) под `/admin/*`; `CreateProfile`/`UpdateProfile`/`DeactivateProfile`/`ListAllProfiles` (`DeactivateProfile` блокирует архивацию `is_default`); реальный health-check Qdrant/OpenRouter/OpenAI через `GET /admin/health` (всегда 200, `all_healthy`-флаг); CLI-паритет (`scripts/index_document.py list/reindex`, `scripts/check_services.py`). Финальный аудит исправил интеграционные мелочи, найденные по ходу самих задач (dangling-импорт мёртвого `AdminAuthPort` в живом `composition/container.py`; циклы импорта, потребовавшие локальных импортов роутеров внутри `create_application()`). Admin CRUD каталога моделей и admin-управление памятью cross-user — явно отклонены пользователем при планировании, не Sprint 8. 842 теста.

Между записями встречаются пробелы («Sprint 6 задокументирован задним числом», «нет отдельной записи Sprint 9/10 перед Sprint 11») — это упущения процесса ведения этого файла в соответствующих сессиях, не потеря функциональности; при сомнении в фактическом состоянии кода — проверять `git log`, не полагаться только на этот файл.

---

# 33. План следующих спринтов

Пройдено: пользователи/диалоги/история (Sprint 2), профили (Sprint 3), Prompt Engine (Sprint 4), память (Sprint 5), RAG (Sprint 6), каталог моделей (Sprint 7), административные функции (Sprint 8, см. §32).

Явно НЕ входит в объём Sprint 8 (отложено на Этап 11 или отклонено пользователем при планировании):

* полноценный просмотр/агрегация логов и метрик, полная иерархия ошибок §17.4 «Плана реализации.md» (`AccessDeniedError`/`ConfigurationError`/`KnowledgeSearchError`, сквозной `correlation_id`) — Этап 11;
* admin CRUD каталога AI-моделей, admin-управление долговременной памятью (`MemoryRecord` cross-user) — отклонено пользователем.

Sprint 11 (текущий) — производственное развёртывание (Этап 13) + генерализация LLM-провайдера; LLM-часть выполнена (§32), остальное (production deployment) не начато.

Порядок может корректироваться, но изменение должно быть зафиксировано в §32.

---

# 34. Критические инварианты проекта

Следующие правила нельзя нарушать даже при сжатии контекста:

1. Проект — модульный монолит, не микросервисы.
2. Бизнес-логика не зависит от Telegram и FastAPI.
3. Бизнес-логика не зависит от конкретного LLM-провайдера.
4. AI-провайдеры подключаются через `LLMProvider`.
5. Инфраструктурные реализации создаются в bootstrap.
6. Промпты формируются централизованно через Prompt Engine.
7. История и долговременная память — разные подсистемы.
8. Память не извлекается бесконтрольно.
9. RAG использует Qdrant.
10. Прикладные данные MVP используют SQLite.
11. Внешние SDK-типы не проникают в application.
12. Каждый этап завершается работоспособным вертикальным срезом.
13. Не добавляется функциональность будущих этапов без задачи.
14. Секреты не хранятся в коде и не логируются.
15. Изменения сопровождаются тестами.

---

# 35. Краткая памятка после сжатия контекста

Если предыдущий контекст недоступен, продолжать работу исходя из следующего:

> «Декодер» — персональный AI-ассистент на Python 3.11. Архитектура: Modular Monolith + Clean Architecture + Ports and Adapters. Основной интерфейс MVP — Telegram. Application не зависит от Telegram, FastAPI, конкретного LLM-провайдера, SQLAlchemy или Qdrant. AI вызывается через порт `LLMProvider`; реализация — `OpenAiCompatibleLLMAdapter` (дженерик OpenAI-Chat-Completions-совместимый, настраивается через `LLM_PROVIDER_*`, Sprint 11, ADR-11.1 — ранее `OpenRouterLLMAdapter`). Все зависимости собираются в bootstrap. Разработка идёт вертикальными срезами. Не добавлять функциональность раньше соответствующего спринта. Перед завершением изменений запускать Ruff, MyPy и pytest.

---

# 36. Журнал текущего состояния

## Реализовано

Полный вертикальный срез Sprint 1–8 работает целиком, включая вход через Telegram и admin REST API. По слоям (актуальное состояние, детали по спринтам — §32):

* `shared/` — `Settings` (все группы §18), structlog-логирование с редактированием чувствительных полей, 6-классовая иерархия ошибок;
* `domain/` — `conversation` (`MessageText`/`ModelId`/`ProviderId`/`Conversation`/`Message`/`MessageRole`), `user` (`User`), `profile` (`UserProfile`/`ProfileStatus`), `prompt` (`PromptTemplate`/`PromptContext`/`PromptBuildResult`/`TokenBudgetPolicy`), `memory` (`MemoryRecord` + 4 enum), `knowledge`, `model_catalog` (`AIModel`+enum+`GenerationSettings`+`ModelSelection`) — ни один не импортирует SQLAlchemy/Telegram/FastAPI (проверяется grep'ом на каждом спринте);
* `application/` — порты (`LLMProvider`, `UserRepository`, `ConversationRepository`/`MessageRepository`, `ProfileRepository`, `PromptBuilder`/`PromptTemplateRepository`, `MemoryRepository`, `KnowledgeDocumentRepository`, `ModelCatalogRepository`/`ModelSelectionRepository`, `ServiceHealthCheck`) + use cases по каждому домену + `ProcessUserMessage`/`StartNewConversation`/`ClearConversation` как основные сценарии диалога;
* `infrastructure/` — `llm/openrouter_adapter.py` (`OpenAiCompatibleLLMAdapter`), `persistence/` (SQLAlchemy ORM+mappers+репозитории для всех сущностей), `prompts/` (файловые шаблоны), `model_catalog/` (файловый каталог), `documents`/`embeddings`/`qdrant` (RAG), `health/` (3 адаптера);
* `presentation/telegram/` — `/start`, `/new`, `/clear`, `/profile`, `/remember`+`/memory`, `/model`, текстовый хендлер — единственное место, вызывающее `ProcessUserMessage`;
* `presentation/api/` — `/health`, `/admin/health`, `/admin/documents/*`, `/admin/profiles/*`, все admin-роуты за `require_admin_api_key`;
* `bootstrap/` — `container.py`/`repositories.py`/`knowledge_container.py`/`database.py`/`application.py` — единственная точка сборки, одна `ConversationRepositoriesFactory` на всё приложение;
* Docker/Alembic — образ + `docker-compose.yml` (api/telegram-bot/qdrant, именованный volume для SQLite), 6+ Alembic-миграций, `alembic check` чист;
* тесты — 842 (unit/integration/e2e), ruff/ruff format/mypy проходят.

## В разработке

Sprint 11: LLM-провайдер генерализован (S11-01/S11-02), production deployment (Этап 13) — не начат.

## Не реализовано

* Полноценный просмотр/агрегация логов и метрик, `AccessDeniedError`/`ConfigurationError`/`KnowledgeSearchError`, сквозной `correlation_id` через весь стек — Этап 11, отложено пользователем при планировании Sprint 8.
* Admin CRUD каталога AI-моделей, admin-управление долговременной памятью (`MemoryRecord` cross-user) — отклонено пользователем при планировании Sprint 8.
* `UpdateMemoryRecord`, команда `/forget`, векторный поиск по памяти — сознательно не реализованы (ADR-5.9/5.10/5.6, нет вызывающего сценария без admin-интерфейса либо явно заменены проще устроенной альтернативой).
* Реальные прямые (не через OpenRouter/дженерик-совместимый) адаптеры провайдеров, интеллектуальная авто-маршрутизация между моделями, редактирование каталога моделей через Telegram/HTTP — отложено до стабилизации интерфейса (ADR-7.1/7.4).
* `UserProfile.preferred_model` — не читается/не пишется (ADR-7.6): персональный выбор модели идёт через отдельный `ModelSelection`, не через это поле.

## Известные расхождения

**В репозитории одновременно существуют два несовместимых дерева исходного кода.** До прочтения этого файла (в отдельной, более ранней сессии) была выполнена большая миграция по `docs/versions/*_v2.0.md`: `composition/`, `interfaces/`, и остатки `domain/`/`application/`-модулей `ai_core`, `admin`, `rag`, `session`, `skills`, `knowledge_base`, `infrastructure/model_gateway`, `infrastructure/vector_storage`, `shared/domain/identifiers.py` — построены по архитектуре, отличной от этого файла (`interfaces/`+`composition/`, не `presentation/`+`bootstrap/`).

Осознанное решение пользователя: **не реконсилировать целиком**. Каждый спринт, добавляя настоящий аналог того или иного узла (профили, память, prompt engine, каталог моделей, admin), точечно удаляет пересекающуюся часть старого дерева и любые dangling-импорты на неё (задокументировано в сообщениях коммитов каждого спринта: S4-01, S5-01, S6-01 (по факту), S7-01, S8-01) — но не идёт дальше своего непосредственного пересечения. На момент Sprint 8 остаются нетронутыми: `rag`, `session`, `skills`, `knowledge_base`, `shared/domain/identifiers.py`, `interfaces/`, и большая часть `composition/`. Полная реконсиляция — решение, которое нужно принимать явно и отдельно (см. §31), не предпринимать без явного запроса.

## Известные технические нюансы (не самоочевидны из кода)

* **SQLite `trim(X)` без второго аргумента** обрезает только пробелы (0x20), не табы/переводы строк — CHECK-ограничение на непустой `content` использует `trim(content, ' ' || char(9) || char(10) || char(13))`, иначе строка из одних табов проходит как «непустая» (S2-02).
* **`aiosqlite`-соединения привязаны к event loop'у, в котором были открыты.** `Application.run_polling()` создаёт собственный loop — инициализация БД (`init_database()`) и сборка контейнера должны происходить внутри `post_init`/`post_shutdown`, не до `run_polling()` (S2-01/S2-06).
* **SQLite не сохраняет tzinfo.** `DateTime(timezone=True)` возвращает *naive* `datetime` после round-trip через `aiosqlite` — mapper'ы явно снимают tzinfo перед записью и восстанавливают `tzinfo=UTC` при чтении (S2-02).
* **Лексикографическая сортировка строк ломает порядок приоритета.** `'medium' > 'low' > 'high'` по алфавиту — сортировка `MemoryRecord` по `confidence` использует явный `CASE`-ранг, не `ORDER BY confidence` (S5-04).
* **Гонки на `get_or_create_*`/upsert разрешаются исключительно уникальным ограничением БД**, не проверкой на уровне Python: `SELECT` → `INSERT` → при `IntegrityError` откат и повторный `SELECT`, с проверкой, что ошибка именно про нужное ограничение (S2-03/S2-04).
* **Каталоги/шаблоны без `__init__.py` не попадают в wheel без явного `package-data`.** `infrastructure/prompts/templates/*` и `infrastructure/model_catalog/catalog.json` требуют записи в `pyproject.toml::[tool.setuptools.package-data]`, иначе `pip install .` (используется в `Dockerfile`) молча соберёт образ без них — падение обнаруживается только внутри контейнера (S4-04/S7-03).
* **Docker-образ не даёт непривилегированному пользователю писать в `/app/data`/не копирует `alembic.ini` без явных инструкций** — `WORKDIR`/`COPY` выполняются от `root` до `USER dekoder`; нужны явные `mkdir`+`chown` и `COPY alembic.ini`/`COPY alembic` (S2-11/S3-09).
* **Удаление узла мёртвого v2.0-дерева почти всегда тянет dangling-импорты за пределы формально названного в задаче файла** — обычно в `application/ai_core/*`, иногда в живой `composition/container.py`; каждый раз находится и точечно зачищается по ходу задачи, не откладывается (S5-01/S7-01/S8-01).

## Следующее действие

Sprint 11: LLM-провайдер генерализован под дженерик OpenAI-Chat-Completions-совместимый адаптер (S11-01/S11-02, причина — географическая недоступность OpenRouter). Остаток Sprint 11 (production deployment, Этап 13 — backup/restore, CI/CD, диагностика типовых ошибок, судя по `README.md`/недавним коммитам) — в процессе, не завершён этим файлом. Перед продолжением — свериться с `git log`/текущим README на предмет фактического прогресса, этот файл мог отстать от кода (см. «Известные расхождения» про пробелы в ведении журнала).
