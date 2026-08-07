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

Основная задача разработки — создать расширяемую систему, в которой бизнес-логика не зависит от Telegram, FastAPI, OpenRouter, конкретной базы данных или конкретной AI-модели.

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
OpenRouter Adapter
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
domain → OpenRouter
domain → SQLAlchemy
domain → Qdrant
domain → LangChain

application → Telegram
application → FastAPI
application → OpenRouter
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

**Текущее фактическое состояние (после сессии реализации Спринта 1):**
реально используется дерево `domain/conversation/`, `application/conversation/`
(`dto.py`, `ports.py`, `use_cases/process_user_message.py`),
`infrastructure/llm/` (`schemas.py`, `openrouter_adapter.py`), `bootstrap/`
(`container.py`, `application.py`) и `shared/` (`config.py`, `logging.py`,
`errors.py`). `main.py` вызывает `bootstrap.application.create_application`.

Отдельно, **параллельно и не используется реально запускаемым
приложением**, в репозитории существует более крупное дерево-заглушка
(`composition/`, `interfaces/`, а также `domain/`/`application/`-модули
`ai_core`, `admin`, `profile`, `memory`, `knowledge_base`, `rag`,
`model_catalog`, `logging`, `llm` под `infrastructure/model_gateway/`) —
результат отдельной, более ранней и гораздо более крупной миграции по
документам `docs/versions/*_v2.0.md`, выполненной **до** прочтения этого
файла и по своей собственной, отличной от Спринта 1 архитектуре
(`interfaces/`+`composition/` вместо `presentation/`+`bootstrap/`, другой
набор модулей). Реконсиляция этих двух деревьев — осознанно отложенное
решение (см. §36, «Известные расхождения»), не предпринимать её без
явного запроса.

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

Application определяет, **что** должна выполнить система, но не знает, **как технически** вызывается Telegram, OpenRouter, SQLite или Qdrant.

---

## 8.3 Infrastructure

Infrastructure содержит реализации портов:

* OpenRouter Adapter;
* другие LLM-адаптеры;
* SQLAlchemy repositories;
* Qdrant repository;
* парсеры PDF, DOCX и TXT;
* embedding adapters;
* файловое хранилище;
* внешние HTTP-клиенты.

Infrastructure не должна содержать бизнес-решения.

Например, OpenRouter Adapter не решает:

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

* OpenRouter JSON;
* OpenAI SDK objects;
* LangChain messages;
* `httpx.Response`;
* Telegram Update.

Первая реализация:

```text
OpenRouterLLMAdapter
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

После полной реализации MVP он должен координировать:

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

Однако эти функции добавляются поэтапно.

Не следует сразу превращать `ProcessUserMessage` в огромный класс.

При росте сценария логика должна делегироваться отдельным use cases и application services:

* `BuildConversationContext`;
* `FindRelevantMemory`;
* `SearchKnowledge`;
* `BuildPrompt`;
* `ResolveSelectedModel`.

---

# 12. Prompt Engine

Prompt Engine является централизованным компонентом формирования запроса к AI.

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
* в OpenRouter Adapter;
* в FastAPI routes;
* в случайных участках use cases.

До отдельного этапа Prompt Engine допускается временный минимальный системный промпт, передаваемый в `ProcessUserMessage` как зависимость.

---

# 13. Диалоги и история

Основные будущие сущности:

* `User`;
* `Conversation`;
* `Message`;
* `MessageRole`;
* `ConversationStatus`.

Правила:

* диалог принадлежит одному пользователю;
* сообщение принадлежит одному диалогу;
* история пользователей изолирована;
* завершённый диалог не изменяется;
* контекст модели ограничивается отдельной политикой;
* история диалога не является долговременной памятью.

Не передавать модели всю историю без ограничений.

Для ограничения контекста должен использоваться отдельный компонент:

```text
ConversationContextPolicy
```

---

# 14. Пользовательские профили

Профиль определяет:

* стиль;
* тон;
* целевую аудиторию;
* правила ответа;
* структуру;
* ограничения;
* при необходимости предпочтительную модель.

Правила:

* пользователь может иметь несколько профилей;
* один профиль активен;
* профиль по умолчанию всегда доступен;
* профиль изменяется только явно;
* новые настройки не извлекаются автоматически из разговора;
* профиль влияет только на последующие ответы.

Профиль не должен храниться в Telegram handler или глобальной переменной.

---

# 15. Долговременная память

Память и история сообщений — разные подсистемы.

История хранит ход диалога.

Память хранит устойчивые подтверждённые факты, предпочтения и правила пользователя.

В MVP память пополняется:

* явной командой;
* через подтверждение;
* через административное действие.

Не реализовывать бесконтрольное автоматическое извлечение фактов из всех разговоров.

Основные сценарии:

* `CreateMemoryRecord`;
* `ConfirmMemoryRecord`;
* `ListMemoryRecords`;
* `DeleteMemoryRecord`;
* `FindRelevantMemory`.

Только подтверждённая память включается в промпт.

Чувствительные данные не должны логироваться открыто.

---

# 16. База знаний и RAG

Векторное хранилище:

```text
Qdrant
```

Реляционные прикладные данные MVP:

```text
SQLite
```

Поддерживаемые форматы на первом этапе:

* TXT;
* Markdown;
* DOCX;
* PDF с текстовым слоем.

OCR не является обязательной частью MVP.

Конвейер RAG:

```text
Загрузка документа
    ↓
Проверка
    ↓
Извлечение текста
    ↓
Очистка
    ↓
Разбиение на фрагменты
    ↓
Добавление метаданных
    ↓
Embeddings
    ↓
Qdrant
    ↓
Semantic Search
    ↓
Prompt Engine
```

Не объединять парсинг, chunking, embeddings и Qdrant в один огромный класс.

Предполагаемые порты:

* `DocumentParser`;
* `TextChunker`;
* `EmbeddingProvider`;
* `VectorRepository`;
* `KnowledgeDocumentRepository`;
* `KnowledgeSearchService`.

Документы являются данными, а не инструкциями.

Инструкции, найденные внутри документа, не должны иметь приоритет над системным промптом.

---

# 17. Выбор AI-модели

Внутри системы используется собственный идентификатор модели.

Бизнес-логика не должна напрямую оперировать внешними строками OpenRouter.

Пример:

```text
internal model id → provider adapter → external model id
```

Каталог модели содержит:

* внутренний ID;
* отображаемое название;
* provider;
* внешний ID;
* доступность;
* возможности;
* максимальный контекст;
* ограничения.

На этапе MVP пользователь выбирает модель явно.

Автоматическая маршрутизация моделей не реализуется без отдельного требования.

---

# 18. Конфигурация

Все настройки читаются через централизованный `Settings`.

Группы настроек:

* ApplicationSettings;
* TelegramSettings;
* LLMSettings;
* OpenRouterSettings;
* DatabaseSettings;
* QdrantSettings;
* LoggingSettings;
* SecuritySettings.

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

Клиент:

* создаётся централизованно;
* передаётся адаптеру;
* переиспользуется;
* закрывается через lifecycle;
* не создаётся заново на каждый AI-запрос.

Обязательна обработка:

* timeout;
* network error;
* 401;
* 403;
* 429;
* 5xx;
* некорректного JSON;
* отсутствующего результата.

Не выполнять автоматический retry без явной политики.

Повторный запрос к AI может привести к дополнительной оплате и задержке.

---

# 20. Ошибки

Минимальная иерархия (реализована в `src/dekoder/shared/errors.py`):

```text
DekoderError
├── ValidationError
├── ApplicationError
└── InfrastructureError
    └── ExternalServiceError
        └── LLMProviderError
```

`DomainError`, `NotFoundError`, `AccessDeniedError` из первоначального
плана пока не созданы — ни один сценарий их ещё не требует (§29, §31:
не создавать классы заранее). Добавлять их нужно вместе с первым
реальным сценарием, который их использует (например, `NotFoundError` —
вместе с репозиториями следующего спринта), не раньше.

Ошибка должна содержать:

* внутренний код;
* техническое сообщение;
* безопасное пользовательское сообщение;
* необязательную причину;
* необязательные метаданные.

Пользователь не должен видеть:

* stack trace;
* API key;
* URL с секретами;
* внутренний JSON провайдера;
* системный промпт;
* внутренние пути файлов.

Infrastructure errors должны преобразовываться в прикладные ошибки до presentation-слоя.

---

# 21. Логирование

Используется структурированное логирование.

Рекомендуемые поля:

* timestamp;
* level;
* event;
* correlation_id;
* user_id в обезличенном виде;
* conversation_id;
* provider;
* model;
* duration_ms;
* status;
* error_code.

Не логировать:

* API keys;
* Telegram token;
* Authorization header;
* полный текст пользовательского сообщения;
* полный ответ AI;
* полное содержимое памяти;
* чувствительные данные профиля.

Каждый пользовательский запрос должен получать `correlation_id`.

---

# 22. Telegram-интерфейс

Telegram является presentation adapter.

Handler:

1. получает Telegram Update;
2. извлекает необходимые данные;
3. создаёт application command;
4. вызывает use case;
5. преобразует результат в Telegram-ответ;
6. обрабатывает ошибки.

Handler не должен:

* вызывать OpenRouter напрямую;
* читать `.env`;
* обращаться к SQLAlchemy;
* обращаться к Qdrant;
* создавать промпты;
* принимать бизнес-решения.

Длинные сообщения необходимо делить на части с учётом лимита Telegram.

Не использовать глобальное изменяемое состояние для хранения пользовательского контекста.

---

# 23. FastAPI

FastAPI используется для:

* health endpoints;
* административных endpoints;
* возможных webhooks;
* будущих интеграций.

Routes должны быть тонкими.

Routes не должны:

* содержать SQL-запросы;
* вызывать Qdrant напрямую;
* создавать adapters;
* содержать бизнес-правила.

Фабрика приложения:

```text
create_application
```

Ресурсы должны управляться через lifespan.

---

# 24. База данных

На этапе MVP используется SQLite.

SQLAlchemy и Alembic добавляются, когда появляется первая сохраняемая бизнес-сущность.

Не подключать их раньше реальной необходимости.

Repository interfaces объявляются в application или domain, а SQLAlchemy implementations находятся в infrastructure.

ORM-модели не должны передаваться в presentation.

Прикладной слой не должен принимать `AsyncSession`.

---

# 25. Docker

Один программный пакет может запускаться как несколько процессов:

* API;
* Telegram polling.

Допускается использовать два контейнера из одного образа:

```text
api
telegram-bot
```

Это не делает систему микросервисной.

Не добавлять без необходимости:

* PostgreSQL;
* Redis;
* очереди;
* workers;
* Qdrant до этапа RAG.

Docker image:

* не содержит `.env`;
* запускается не от root;
* использует Python 3.11 slim;
* корректно завершает процессы;
* имеет healthcheck для API.

---

# 26. Тестирование

Каждая новая функция должна сопровождаться тестами.

## Unit tests

Проверяют:

* domain;
* policies;
* use cases;
* Prompt Engine;
* преобразование ошибок;
* бизнес-правила.

Unit tests не вызывают реальные API.

## Integration tests

Проверяют:

* HTTP adapters через mock server;
* repositories;
* SQLite;
* Qdrant;
* parsers;
* Telegram handlers;
* FastAPI routes.

Для OpenRouter использовать `respx` или эквивалент.

## Acceptance tests

Проверяют основные пользовательские сценарии.

Не сравнивать полный текст недетерминированного ответа реальной модели.

Проверять:

* факт вызова;
* сформированный запрос;
* структуру ответа;
* ошибки;
* переданные метаданные.

---

# 27. Инструменты качества

Перед завершением задачи должны проходить:

```bash
ruff format --check .
ruff check .
mypy src
pytest
```

При необходимости:

```bash
pytest --cov=dekoder --cov-report=term-missing
```

Не отключать проверки глобально ради исправления одной ошибки.

Не использовать массово:

```python
# type: ignore
```

Каждое исключение должно быть обосновано.

---

# 28. Правила именования

Предпочтительны имена, выражающие бизнес-смысл:

```text
ProcessUserMessage
BuildConversationContext
FindRelevantMemory
SelectProfile
SearchKnowledge
OpenRouterLLMAdapter
ConversationRepository
```

Избегать безликих имён:

```text
Manager
Helper
Utils
Processor
Common
BaseService
DataHandler
```

если ответственность из имени неясна.

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

При получении задачи Claude Code не должен автоматически:

* переписывать всю архитектуру;
* переименовывать множество файлов;
* менять публичные интерфейсы без необходимости;
* подключать новые библиотеки;
* добавлять будущие модули;
* создавать сложные абстракции;
* исправлять несвязанные участки кода;
* удалять архитектурные документы.

---

# 30. Формат выполнения задач

Для каждой задачи использовать следующий порядок.

## Шаг 1. Анализ

Указать:

* какие файлы уже существуют;
* какие компоненты затрагиваются;
* какие архитектурные ограничения применимы;
* есть ли противоречия.

## Шаг 2. План изменений

Кратко перечислить:

* создаваемые файлы;
* изменяемые файлы;
* тесты;
* возможные миграции;
* зависимости.

## Шаг 3. Реализация

Внести только изменения, необходимые для текущей задачи.

## Шаг 4. Проверка

Запустить:

```bash
ruff format --check .
ruff check .
mypy src
pytest
```

## Шаг 5. Отчёт

Сообщить:

* что реализовано;
* какие файлы изменены;
* какие проверки пройдены;
* какие ограничения остались;
* есть ли технический долг.

---

# 31. Запрет на скрытое изменение архитектуры

Если текущая задача требует отступления от архитектуры, Claude Code должен:

1. не вносить изменение молча;
2. объяснить противоречие;
3. предложить минимальный вариант;
4. дождаться отдельного решения, если изменение существенное.

Существенными считаются:

* смена архитектурного стиля;
* добавление микросервиса;
* замена базы данных;
* изменение направления зависимостей;
* удаление порта;
* перенос бизнес-логики в infrastructure;
* добавление нового AI-фреймворка;
* изменение публичных контрактов нескольких модулей.

---

# 32. Текущий этап разработки

Перед началом новой сессии обновлять этот раздел.

## Текущий спринт

**Спринт 1: технический фундамент и Walking Skeleton.**

## Цель спринта

Реализовать:

```text
Telegram
→ ProcessUserMessage
→ LLMProvider
→ OpenRouterLLMAdapter
→ Telegram response
```

## В текущий спринт входят

* [x] базовый Python-проект;
* [x] FastAPI;
* [x] `/health`;
* [x] централизованные настройки (`shared/config.py`, pydantic-settings);
* [x] базовое логирование (`shared/logging.py`, structlog);
* [x] базовые ошибки (`shared/errors.py`, см. §20);
* [x] `MessageText` (+ `ModelId`, `ProviderId` — `domain/conversation/value_objects.py`);
* [x] внутренние DTO (`application/conversation/dto.py`);
* [x] `LLMProvider` (`application/conversation/ports.py`);
* [x] `ProcessUserMessage` (`application/conversation/use_cases/process_user_message.py`);
* [x] OpenRouter Adapter (`infrastructure/llm/openrouter_adapter.py`);
* [x] bootstrap-слой без DI-библиотеки (`bootstrap/container.py`, `bootstrap/application.py`);
* [x] Telegram `/start`;
* [x] обработка текстового сообщения (Telegram → `ProcessUserMessage`);
* [x] Docker;
* [x] тесты (unit + integration + сквозной e2e-сценарий диалога, `tests/e2e/`);
* [x] README (описывает реально работающий срез, а не `docs/versions/*_v2.0.md`).

Спринт 1 завершён: вертикальный срез
`Telegram → ProcessUserMessage → LLMProvider → OpenRouter → ответ`
работает целиком, ruff/mypy/pytest проходят (143 теста).

## В текущий спринт не входят

* SQLAlchemy;
* Alembic;
* SQLite;
* User;
* Conversation;
* Message entity;
* история;
* профили;
* Prompt Engine;
* память;
* Qdrant;
* RAG;
* выбор модели;
* административные функции.

Не реализовывать эти функции в рамках спринта 1.

## Текущий спринт (обновление)

**Спринт 2: постоянное хранилище данных, диалоги, история — завершён
(S2-01…S2-11).**

Цель и полный состав спринта — внешняя архитектурная спецификация
`backlog_2.md` (не входит в этот репозиторий) и §33 ниже. Прогресс по
задачам:

* [x] S2-01 — подключение SQLAlchemy 2.x (async) и Alembic: только
  инфраструктура (`infrastructure/persistence/`, `alembic/`,
  `bootstrap/database.py`), без ORM-моделей, репозиториев и таблиц —
  см. §36 для подробностей;
* [x] S2-02 — доменные сущности `User`/`Conversation`/`Message`,
  ORM-модели, mapper Domain↔ORM, первая Alembic-миграция схемы
  (`users`/`conversations`/`messages` + внешние ключи/индексы/
  ограничения) — см. §36 для подробностей;
* [x] S2-03 — `UserRepository`: порт (`application/user/ports.py`) +
  SQLAlchemy-реализация (`infrastructure/persistence/user_repository.py`)
  + bootstrap-фабрика (`bootstrap/repositories.py`) — см. §36 для
  подробностей;
* [x] S2-04 — `ConversationRepository`: порт
  (`application/conversation/ports.py`, рядом с `LLMProvider`) +
  SQLAlchemy-реализация
  (`infrastructure/persistence/conversation_repository.py`) +
  bootstrap-фабрика (`bootstrap/repositories.py`) — см. §36 для
  подробностей;
* [x] S2-05 — `MessageRepository`: порт (`application/conversation/
  ports.py`, рядом с `LLMProvider`/`ConversationRepository`) +
  SQLAlchemy-реализация
  (`infrastructure/persistence/message_repository.py`) + bootstrap-фабрика
  (`bootstrap/repositories.py`) — репозитории для Sprint 2 завершены, см.
  §36 для подробностей;
* [x] S2-06 — расширение `ProcessUserMessage` историей диалога: теперь
  идентифицирует пользователя, получает/создаёт активный диалог,
  сохраняет сообщения (короткие транзакции ДО и ПОСЛЕ вызова LLM) и
  формирует LLM-контекст из истории (впервые подключены все три
  репозитория) — см. §36 для подробностей;
* [x] S2-07 — `StartNewConversation` use case (`application/conversation/
  use_cases/start_new_conversation.py`): закрывает текущий активный диалог
  пользователя (если есть) через доменный `Conversation.close()` и
  создаёт новый пустой активный диалог; не создаёт пользователя
  автоматически (отличие от `ProcessUserMessage`); не использует
  `MessageRepository`, не вызывает LLM; `/new` к Telegram Adapter не
  подключена — см. §36 для подробностей;
* [x] S2-08 — подключение команды `/new` в Telegram Adapter: новый
  `NewConversationHandler` (`presentation/telegram/handlers/
  new_conversation.py`) вызывает `StartNewConversation`, зарегистрирован
  `CommandHandler("new", ...)` внутри `post_init` (`bot.py::
  register_new_conversation_handler`, `telegram_main.py`); контейнер
  собирает `StartNewConversation` поверх той же `repositories_factory`,
  что и `ProcessUserMessage` — см. §36 для подробностей;
* [x] S2-09 — `ClearConversation` use case (`application/conversation/
  use_cases/clear_conversation.py`): удаляет все сообщения ТЕКУЩЕГО
  активного диалога пользователя через `MessageRepository.clear()`, не
  закрывая и не удаляя сам `Conversation`; не создаёт пользователя и не
  создаёт диалог автоматически (как и `StartNewConversation`); результат
  (`ClearConversationResult.status: ClearConversationStatus`) различает
  три исхода — `CLEARED`/`ALREADY_EMPTY`/`NO_ACTIVE_CONVERSATION`; не
  принимает `LLMProvider`; `/clear` к Telegram Adapter не подключена —
  следующая задача S2-10 — см. §36 для подробностей;
* [x] S2-10 — подключение команды `/clear` в Telegram Adapter: новый
  `ClearConversationHandler` (`presentation/telegram/handlers/
  clear_conversation.py`) вызывает `ClearConversation`, каждый из трёх
  статусов результата переводится в отдельное сообщение пользователю;
  зарегистрирован `CommandHandler("clear", ...)` внутри `post_init`
  (`bot.py::register_clear_conversation_handler`, `telegram_main.py`);
  контейнер собирает `ClearConversation` поверх той же
  `repositories_factory`, что и `ProcessUserMessage`/`StartNewConversation`
  — Спринт 2 функционально завершён, следующая задача (S2-11) —
  финальная интеграция/ревью спринта — см. §36 для подробностей;
* [x] S2-11 — финальная интеграция и E2E-проверка: полный аудит
  composition root/DI/транзакций/конфигурации/миграций Sprint 2 не выявил
  необходимости в архитектурных изменениях (все компоненты S2-01…S2-10
  уже были корректно подключены) — найдены и точечно исправлены три
  реальных интеграционных дефекта: (1) неустойчивый порядок сообщений в
  `MessageRepository.history()` при совпадении `created_at` (грубое
  разрешение системных часов + случайный UUID как вторичный ключ
  сортировки, S2-05) — исправлено в `ProcessUserMessage._build_message`
  (гарантия строго возрастающего `created_at` в рамках одного экземпляра,
  без изменений ORM/схемы/репозиториев); (2) `Dockerfile` не давал
  непривилегированному пользователю `dekoder` создать `/app/data`
  (`mkdir: Permission denied`, оба сервиса падали бы при старте на
  `init_database()`) — исправлено явным `mkdir`+`chown` каталога данных
  до `USER dekoder`; (3) `docker-compose.yml` не монтировал `/app/data` ни
  в один volume — SQLite-файл жил только в слое контейнера и терялся при
  каждом `docker compose down`/пересборке образа — исправлено общим
  именованным volume `dekoder_data` для `api`/`telegram-bot`. Все три
  находки подтверждены эмпирически (флейки-тест до/после фикса; реальная
  сборка и запуск Docker-образа; `docker compose down && up` с проверкой
  файла на volume). Добавлен `tests/e2e/test_conversation_persistence_scenario.py`
  (8 тестов, реальная временная SQLite поверх `bootstrap/repositories.py`,
  тот же Telegram-хендлер-харнесс, что и в `tests/e2e/
  test_conversation_scenario.py`) — восемь обязательных сценариев
  backlog_2_tasks.md (первый/второй запрос, `/new`, `/clear`, изоляция
  пользователей, перезапуск приложения на том же файле БД, ошибка LLM,
  ошибка БД/rollback). README обновлён под фактическое состояние Sprint 2
  (миграции, `/new`/`/clear`, тесты). Новая бизнес-функциональность не
  добавлена — Спринт 2 (S2-01…S2-11) полностью завершён, 354 теста,
  ruff/ruff format/mypy проходят — см. §36 для подробностей.

## Текущий спринт (обновление 2)

**Спринт 3: пользовательские профили — персонализация системной
инструкции — завершён (S3-01…S3-09).**

Цель и полный состав спринта — внешняя архитектурная спецификация
`backlog_3.md` (не входит в этот репозиторий) и §33 ниже. Прогресс по
задачам:

* [x] S3-01 — удаление мёртвого скелета профилей v2.0-архитектуры:
  удалены `domain/profile/profile.py` (`AuthorProfile`/`ProfileSettings`/
  старый `ProfileStatus`), весь `application/profile/{ports,commands,
  queries}.py` и `application/profile/use_cases/*` (семь use case'ов,
  все `raise NotImplementedError`), `infrastructure/persistence/
  sqlite_profile_repository.py`; точечно зачищены dangling-импорты на
  удалённые типы из пяти файлов недостижимого v2.0-скелета
  (`application/ai_core/use_cases/route_command.py` —
  `AuthorProfileView` и пять use case'ов профиля плюс метод
  `list_profiles`; `generate_content.py` — `GetAuthorProfileUseCase` и
  параметр конструктора; `execution_context_builder.py`/`shared/
  application/execution_context.py` — параметр/поле `profile:
  AuthorProfile`; `composition/container.py` — поле `Container.
  profile_repository`), без изменения остального поведения этих файлов;
  `domain/profile/`/`application/profile/` оставлены как пустые пакеты
  (только `__init__.py`), готовые к S3-02. Реальный код Sprint 1–2
  (`presentation/`, `bootstrap/`, `domain/{user,conversation}`,
  `application/{user,conversation}`, `infrastructure/{llm,persistence}`
  за пределами удалённого файла) не тронут; остальной v2.0-скелет
  (`admin`, `memory`, `rag`, `model_catalog`, `session`,
  `knowledge_base`, `skills`, `infrastructure/model_gateway`,
  `infrastructure/vector_storage`, `interfaces/` за пределами
  перечисленных пяти файлов) не тронут — см. §36 для подробностей.
* [x] S3-02 — доменные сущности `UserProfile`/`ProfileStatus`
  (`domain/profile/{entities.py,value_objects.py}`): один
  `frozen=True, slots=True` датакласс `UserProfile` со всеми
  описательными полями ADR-3.5 как примитивами (`forbidden_phrasing:
  tuple[str, ...]`, `preferred_model: ModelId | None` — переиспользует
  `domain/conversation/value_objects.ModelId`, не дублируется),
  `id: UUID` без обёртки-VO; `ProfileStatus(Enum)` — только
  `ACTIVE`/`ARCHIVED` (не `CREATED`, которое было в удалённом S3-01
  скелете). Инварианты (`__post_init__`): непустое `name`, непустое
  `system_instruction`, `updated_at >= created_at` — обычный
  `ValueError`, без нового класса доменной ошибки. Ноль зависимостей от
  SQLAlchemy/Telegram/FastAPI (подтверждено grep). `ProfileId`/
  `TonePreset`/`ProfilePrompt`/`ProfilePreferences` как отдельные типы
  не созданы (ADR-3.5). ORM-модели, миграция, репозиторий и use case'ы
  ещё не существуют — следующая задача S3-03 — см. §36 для
  подробностей.
* [x] S3-03 — ORM-модели и схемная миграция профилей: `ProfileORM`
  (`infrastructure/persistence/profile_orm.py`) и
  `UserActiveProfileORM` (`infrastructure/persistence/
  user_active_profile_orm.py`) точно по модели данных `backlog_3.md §5`
  (`forbidden_phrasing` — `sa.JSON`, `status` — `String`+`CheckConstraint`
  `ck_profiles_status`, частичный уникальный индекс
  `uq_profiles_is_default` с `sqlite_where="is_default = 1"` по образцу
  `uq_conversations_active_user`); `profile_to_orm`/`profile_to_domain`
  добавлены в `mappers.py` с той же дисциплиной таймстемпов
  (`_to_naive_utc`/`_to_aware_utc`), что и у существующих мапперов;
  `UserActiveProfileORM` сознательно не получил мапперы — не доменная
  сущность (ADR-3.1), инкапсулирована целиком за `ProfileRepository`
  (следующая задача S3-05). Новая Alembic-ревизия `14bf7e3ae815`
  (`down_revision = "a96ab72bfa8a"`, существующая миграция S2-02 не
  изменена) создаёт `profiles` → `user_active_profiles` → частичный
  индекс, `downgrade()` — строго в обратном порядке; сгенерирована
  `alembic revision --autogenerate` (против временной базы, поднятой до
  ревизии S2-02) и вручную выверена. Сид-данные ещё не вносятся —
  следующая задача S3-04. Эмпирически проверено: `upgrade head` →
  `downgrade -1` → `upgrade head` на временной SQLite проходит без
  ошибок, `downgrade -1` удаляет только `profiles`/`user_active_profiles`,
  не трогая `users`/`conversations`/`messages` — см. §36 для подробностей.
* [x] S3-04 — сид-миграция каталога профилей: новая Alembic-ревизия
  `27c4e9f2a103` (`down_revision = "14bf7e3ae815"`) вносит 4
  предустановленных профиля через `op.bulk_insert` с детерминированными
  UUID-константами (`PROFILE_EXPERT_ID`/`PROFILE_FRIENDLY_ID`/
  `PROFILE_BUSINESS_ID`/`PROFILE_CREATIVE_ID`, не `uuid4()`) — «Экспертный»,
  «Дружелюбный», «Деловой» (`is_default=True`), «Креативный»; текст —
  черновой состав из backlog_3_tasks.md S3-04, принят как рабочий вариант
  (финальный копирайтинг может потребовать отдельной миграции после
  Sprint 3, см. ADR-3.4 «Недостатки» — явно помечено в docstring
  миграции). «Деловой» выбран дефолтом как ближайший по духу к прежнему
  `_DEFAULT_SYSTEM_PROMPT` («Отвечай кратко и по делу»). `downgrade()`
  удаляет ровно эти 4 строки по `id` (`DELETE ... WHERE id IN (...)`),
  никогда `DELETE FROM profiles` без `WHERE`. Эмпирически проверено:
  `upgrade head` создаёт ровно 4 строки, все `status='active'`,
  `is_system=true`, ровно одна `is_default=true`; `downgrade -1` оставляет
  таблицу `profiles` пустой, но не удаляет её (схема остаётся); повторный
  `upgrade head` восстанавливает те же 4 строки с теми же `id`. Use
  case'ы, читающие каталог, ещё не существуют — следующая задача S3-05
  (`ProfileRepository`) — см. §36 для подробностей.
* [x] S3-05 — `ProfileRepository`: порт (`application/profile/
  ports.py`, `Protocol`+`@runtime_checkable`, только доменные/stdlib
  типы в сигнатурах) + `SQLAlchemyProfileRepository`
  (`infrastructure/persistence/profile_repository.py`). `get_active_
  profile` — один SQL-запрос (`LEFT JOIN` от однострочной
  «области видимости» пользователя на `user_active_profiles`, затем
  `JOIN` на `profiles` по `COALESCE(profile_id, id профиля-дефолта)`),
  не два последовательных запроса с проверкой на уровне Python;
  прототип запроса проверен вручную перед встраиванием в репозиторий.
  `select_profile` — атомарный upsert (`sqlite.insert(...).
  on_conflict_do_update(...)` по `user_id`) после проверки
  `status='active'` целевого `profile_id`; неизвестный/неактивный
  `profile_id` → `None`, ничего не записывая. `ConversationRepositories`
  (`application/conversation/ports.py`, ADR-3.3) получила обязательное
  поле `profiles: ProfileRepository` — никакой второй фабрики
  репозиториев не введено (подтверждено grep). Поскольку поле
  обязательное, часть объёма, нормально закреплённого за S3-06
  (`FakeProfileRepository` в `tests/support/
  fake_conversation_repositories.py`, расширение
  `make_in_memory_repositories_factory` параметром `profiles`),
  пришлось перенести в эту же задачу — иначе существующие тесты Sprint 2
  перестали бы собираться сразу после добавления поля; S3-06 не будет
  переделывать эту инфраструктуру, только добавит три use case'а поверх
  неё. `bootstrap/repositories.py::build_profile_repository` подключён в
  `build_conversation_repositories_factory` рядом с тремя существующими
  билдерами. Тесты: Protocol-соответствие
  (`tests/unit/application/test_profile_repository_port.py`) и
  интеграционные на реальной SQLite
  (`tests/integration/persistence/test_profile_repository.py`) —
  дефолт без выбора, сохранение выбора, замена выбора без дублирования
  строки, отказ на неизвестный/архивный `profile_id`, изоляция между
  пользователями — см. §36 для подробностей.
* [x] S3-06 — use cases `ListProfiles`/`GetActiveProfile`/
  `SelectProfile` (`application/profile/{dto.py,use_cases/
  {list_profiles,get_active_profile,select_profile}.py}`) — тот же
  стиль, что и `StartNewConversation`/`ClearConversation` (S2-07/S2-09):
  каждый принимает только `ConversationRepositoriesFactory`, использует
  `repositories.profiles` (и `repositories.users` для двух последних),
  одна короткая транзакция на вызов. `GetActiveProfile`/`SelectProfile`
  используют `get_by_telegram_user_id` (не `get_or_create_...`) — не
  создают пользователя побочным эффектом просмотра/выбора профиля,
  подтверждено grep. `SelectProfile` возвращает явный статус
  (`SELECTED`/`UNKNOWN_USER`/`UNKNOWN_PROFILE`), не исключение, на
  ожидаемые отрицательные исходы — по образцу `ClearConversationStatus`.
  Подключены в `ApplicationContainer`/`build_container`
  (`bootstrap/container.py`) поверх той же `repositories_factory`, что и
  остальные use case'ы — второй фабрики не появилось. `FakeProfileRepository`
  и расширение `make_in_memory_repositories_factory` уже существовали с
  S3-05 (пришлось перенести туда раньше срока) — эта задача их только
  использует, не создаёт заново. Тесты — все на `FakeProfileRepository`/
  `FakeUserRepository`, без SQLAlchemy: список всех активных профилей и
  исключение архивных, `profile=None` для неизвестного пользователя,
  дефолт без выбора против сохранённого выбора, `UNKNOWN_USER`/
  `UNKNOWN_PROFILE`/`SELECTED` с проверкой, что выбор не меняется при
  отказе — см. §36 для подробностей.
* [x] S3-07 — интеграция активного профиля в `ProcessUserMessage`
  (ADR-3.3): `_save_user_message` (транзакция 1) сразу после
  получения/создания `User`/`Conversation` дополнительно читает
  `repositories.profiles.get_active_profile(user.id)` тем же вызовом
  `self._repositories()` — без отдельной транзакции — и возвращает
  `(conversation_id, system_instruction)`; `execute()` подставляет
  `system_instruction` в `LLMRequest.system_prompt`. Конструктор
  переименовал параметр `system_prompt` → `default_system_prompt`
  (используется только как fallback при пустой после `strip()`
  инструкции профиля — не должно происходить в норме, ADR-3.2/3.5
  гарантируют непустую строку, но use case не полагается на это молча);
  переименование выполнено последовательно везде, включая
  `bootstrap/container.py` (именованный аргумент и комментарий к
  `_DEFAULT_SYSTEM_PROMPT` — теперь fallback, не основной путь), кроме
  самого поля `LLMRequest.system_prompt` (DTO, не переименовывается,
  подтверждено grep). Никакого Prompt Engine/шаблонизации не введено —
  прямая подстановка `profile.system_instruction`. Транзакционные
  границы (три короткие транзакции, LLM вне транзакции) не изменились
  по структуре. Существующие тесты Sprint 2 адаптированы под
  обязательное поле `profiles`; там, где реальная SQLite создаётся
  через `Base.metadata.create_all()` (без Alembic сид-миграции —
  S3-04), тестовое окружение вставляет один активный профиль-дефолт
  напрямую через `ProfileORM` (`tests/integration/
  test_process_user_message_persistence.py`, `tests/e2e/
  test_conversation_persistence_scenario.py`) — иначе `get_active_
  profile` падал бы `InfrastructureError` на пустом каталоге. Новые
  тесты: персонализация `system_prompt` из активного профиля, разные
  пользователи с разными выбранными профилями получают разный
  `system_prompt` в рамках одного экземпляра use case, fallback на
  `default_system_prompt` при пустой инструкции — юнит; переключение
  профиля через реальный `ProfileRepository` меняет `system_prompt`
  следующего вызова LLM, не переписывая содержимое уже сохранённых
  сообщений — интеграционный (реальная SQLite) — см. §36 для
  подробностей.
* [x] S3-08 — Telegram-команда `/profile`:
  `presentation/telegram/handlers/profile.py` — `ProfileCommandHandler`
  (`/profile`: вызывает `GetActiveProfile`, при `profile=None`
  — нейтральное сообщение без вызова `ListProfiles`; иначе `ListProfiles`
  и inline-клавиатура с одной кнопкой на профиль, активный отмечен
  суффиксом «(текущий)» в тексте кнопки, не эмодзи) и
  `ProfileSelectionCallbackHandler` (первый `CallbackQueryHandler` в
  проекте, `pattern=r"^profile:"`; `callback_data` кодирует только
  `profile_id` — `_build_profile_keyboard`/`_parse_profile_callback_data`;
  вызывает `SelectProfile`, редактирует исходное сообщение подтверждением
  или явной обработкой `UNKNOWN_USER`/`UNKNOWN_PROFILE`, невалидный/чужой
  `callback_data` тоже приводит к понятному сообщению, не к исключению).
  `mapper.py` расширен `to_get_active_profile_command`/
  `to_select_profile_command` — последний впервые в проекте берёт
  `telegram_user_id` из `update.callback_query.from_user`, не
  `update.effective_user`. `DekoderError` → `error.user_message`, прочие
  исключения → нейтральное сообщение + `_logger.exception` — тот же
  принцип, что и `NewConversationHandler`/`ClearConversationHandler`.
  `register_profile_handlers` (`bot.py`) вызывается из `post_init`
  (`telegram_main.py`), поверх `container.list_profiles`/
  `get_active_profile`/`select_profile`. Presentation-слой по-прежнему
  не импортирует SQLAlchemy/`AsyncSession` (подтверждено grep). Тесты —
  список с отметкой активного, `callback_data` кодирует только
  `profile_id`, выбор через callback переключает профиль без изменения
  при отказе, `UNKNOWN_USER`/`UNKNOWN_PROFILE`/невалидный `callback_data`
  обрабатываются явно, `DekoderError`/неожиданное исключение не
  протекают деталями к пользователю — см. §36 для подробностей.
* [x] S3-09 — финальная интеграция и E2E-проверка Sprint 3: полный
  аудит composition root/DI/транзакций/миграций для профильного среза не
  выявил необходимости в архитектурных изменениях (S3-01…S3-08 уже были
  корректно связаны — `ConversationRepositories.profiles`, единственная
  фабрика репозиториев, `ProcessUserMessage` читает активный профиль
  внутри транзакции 1, presentation-слой без SQLAlchemy). Найден и
  точечно исправлен один реальный интеграционный дефект, не
  архитектурный: `Dockerfile` не копировал `alembic.ini`/`alembic/` в
  образ (только `pyproject.toml`/`src`) — внутри собранного контейнера
  `alembic upgrade head` падал `FAILED: No 'script_location' key found
  in configuration`, то есть инструкция README «примените миграции перед
  первым запуском» была невыполнима для реального Docker-развёртывания;
  ни один существующий тест этого не ловил, так как все интеграционные/
  e2e-тесты запускают `alembic` с хоста, из корня репозитория, где оба
  файла и так присутствуют. Исправлено добавлением `COPY alembic.ini
  ./`/`COPY alembic ./alembic` в `Dockerfile` (после `pip install`, до
  `USER dekoder` — файлы миграций read-only, отдельный `chown` не нужен,
  `.dockerignore` уже отфильтровывает `__pycache__`). Подтверждено
  эмпирически: `docker build` реального образа, `docker run ... alembic
  upgrade head` внутри контейнера (от лица непривилегированного
  `dekoder`, поверх именованного volume) — до фикса падал с указанной
  ошибкой, после — создаёт схему и вносит сид-каталог; `SELECT
  COUNT(*) FROM profiles` = 4, `SELECT COUNT(*) FROM profiles WHERE
  is_default = 1` = 1; `alembic downgrade -1` → `alembic upgrade head`
  внутри того же контейнера — идемпотентно, каталог восстанавливается
  той же четвёркой `id`; отдельно поднят `api`-контейнер с фиктивными
  секретами поверх исправленного образа — `/health` отвечает `200`,
  журнал чистый. Добавлен `tests/e2e/test_profile_scenario.py` (5
  тестов, тот же харнесс, что и `test_conversation_persistence_scenario.py`
  — реальный `telegram.ext.Application`, реальные SQLAlchemy-репозитории,
  единственная подмена `FakeLLMProvider`) — пять обязательных сценариев
  backlog_3_tasks.md (S3-09): дефолтный профиль без выбора; переключение
  через `/profile` влияет на `system_prompt` только будущих сообщений,
  не переписывая уже сохранённые; изоляция между двумя пользователями;
  отказ на callback с несуществующим `profile_id` (активный профиль не
  меняется, LLM не вызывается); полный цикл `/profile` → клавиатура с
  отметкой активного → выбор → подтверждение через реальный
  `CallbackQueryHandler`, не мок. Grep-проверки архитектурных границ —
  все чистые: `sqlalchemy|AsyncSession` в `presentation/telegram/` —
  только докстринг-упоминания; `domain.profile.profile|application\.
  profile\b` — ни одной ссылки на удалённый v2.0-скелет, только новые
  файлы Sprint 3; `ProfileRepositoriesFactory` — ноль совпадений (нет
  второй фабрики). Полный цикл миграций (`downgrade base` → `upgrade
  head` → `downgrade base` → `upgrade head`) воспроизведён и на хосте, и
  внутри Docker-образа — везде идемпотентен. `README.md` обновлён:
  раздел «Что реально работает сейчас» описывает персонализацию через
  активный профиль и `/profile`, дерево каталогов включает `domain/
  profile`/`application/profile`/новые файлы `infrastructure/
  persistence/`, раздел «База данных и миграции» описывает все три
  ревизии (S2-02/S3-03/S3-04), раздел «Тесты» упоминает `test_
  profile_scenario.py`, абзац про мёртвый v2.0-скелет обновлён — `profile`
  убран из списка нереконсилированных модулей. Новая бизнес-функциональность
  не добавлена — Sprint 3 (S3-01…S3-09) полностью завершён, 427 тестов,
  ruff/ruff format/mypy проходят — см. §36 для подробностей.

## Текущий спринт (обновление 3)

**Спринт 4: Prompt Engine — централизованная сборка промпта — завершён
(S4-01…S4-08).**

Цель и полный состав спринта — внешняя архитектурная спецификация
`backlog_4.md` (не входит в этот репозиторий) и §33 ниже. Прогресс по
задачам:

* [x] S4-01 — удаление мёртвого v2.0-скелета логирования
  (`infrastructure/logging/{composite_logger,file_audit_logger,
  stdout_technical_logger}.py`, `application/logging/ports.py::Logger`,
  `domain/logging/entries.py::AuditRecord/TechnicalLogEvent/
  SystemEventEntry`) и мёртвого v2.0-построителя промпта
  (`application/prompt_engine/{ports.py,prompt_builder.py}`,
  `application/ai_core/internal_services/prompt_assembler.py`) — оба
  риска путаницы прямо для этого спринта (правдоподобно выглядящий
  «второй логгер»/«второй построитель промпта» ровно в момент, когда
  строятся настоящие, ADR-4.10, пересмотрено с пользователем — изначально
  `prompt_engine` планировалось не трогать). Точечно зачищены dangling-
  импорты `Logger`/`PromptAssembler`/`PromptBuilder` (мёртвых типов) в
  семи файлах `application/admin/use_cases/*`, двух use case'ах
  `application/ai_core/use_cases/{answer_knowledge_question,
  generate_content}.py`, `composition/container.py`,
  `interfaces/telegram/handlers.py` — убраны только импорт и ставший
  недостижимым параметр конструктора, поведение файлов (`raise
  NotImplementedError`) не изменилось. `application/ai_core/` как
  директория сохранена — удалён только `prompt_assembler.py`. Остальной
  v2.0-скелет (`admin`, `memory`, `rag`, `session`, `skills`,
  `model_catalog`, `knowledge_base`, `model_gateway`,
  `infrastructure/vector_storage`, `interfaces/`, `composition/` за
  пределами точечной зачистки) не тронут — см. §36 для подробностей.
* [x] S4-02 — доменный слой Prompt Engine
  (`domain/prompt/{entities.py,value_objects.py,policies.py}`):
  `PromptTemplate`(+`PromptTemplateStatus`, `ACTIVE`/`ARCHIVED`),
  `PromptSection`, `PromptContext` (`dialogue_history: Sequence[Message]`
  — переиспользует `domain.conversation.entities.Message`, последний
  элемент по соглашению — текущий запрос пользователя, ADR-4.1;
  `confirmed_memory_facts`/`knowledge_fragments: Sequence[str] = ()` —
  плейсхолдеры Этапов 7/8, ADR-4.3, не новые доменные типы),
  `PromptBuildResult` (`messages: Sequence[application.conversation.
  dto.LLMMessage]` — намеренная, документированная узкая зависимость
  domain→application: `LLMMessage` сам не имеет I/O-зависимостей, а
  ADR-4.1 требует, чтобы `ProcessUserMessage` мог передать `result.
  messages` в `LLMRequest` без преобразования). `TokenBudgetPolicy`
  (`domain/prompt/policies.py`) реализована полностью в этой же задаче
  (не только «форма», как изначально предполагал план S4-02, — алгоритм
  тиров ADR-4.5 оказался достаточно простым и детерминированным, чтобы
  не откладывать до S4-06 и не переписывать дважды): 6 тиров сокращения
  строго по приоритету (секции 1/2/3/8 и последнее сообщение
  неприкосновенны; секции 4/5 — no-op в Sprint 4, но реальные
  исполняемые ветки; история обрезается с самого старого элемента).
  Юнит-тесты — валидация сущностей + полная матрица тиров
  `TokenBudgetPolicy` на синтетических данных (включая искусственно
  большие «неприкосновенные» секции). Ноль I/O в `domain/prompt/` за
  пределами документированной зависимости на `LLMMessage` — см. §36 для
  подробностей.
* [x] S4-03 — порты Prompt Engine (`application/prompt/ports.py`):
  `PromptBuilder` (`Protocol`, синхронный `build(context) ->
  PromptBuildResult`, без `@runtime_checkable` — единственная реализация
  внедряется через конструктор, не через fake structural-typing тесты) и
  `PromptTemplateRepository` (`Protocol`, `@runtime_checkable`, по стилю
  `ProfileRepository`/`UserRepository`: `get(name) -> PromptTemplate`
  (поднимает ошибку при отсутствии шаблона — конфигурационная ошибка, не
  штатный `None`), `list_all() -> Sequence[PromptTemplate]`, оба
  синхронные — файлы читаются один раз при построении репозитория, не на
  каждый вызов). `PromptTemplateRepository` не встроен в
  `ConversationRepositories`/`ConversationRepositoriesFactory` — вторая
  фабрика репозиториев не появилась (подтверждено grep) — см. §36 для
  подробностей.
* [x] S4-04 — `infrastructure/prompts/file_template_repository.py::
  FileTemplateRepository` + `infrastructure/prompts/templates/` (JSON-
  манифест + 6 текстовых файлов): `base_instruction` (текст — буквально
  прежняя `_DEFAULT_SYSTEM_PROMPT`, перенесённая из `bootstrap/
  container.py`), `safety_rules`, `profile_parameters` (`string.Template`
  с переменными под все описательные поля `UserProfile`, включая
  предрендеренные опциональные строки `forbidden_phrasing_line`/
  `response_length_line`/`additional_constraints_line` — пустые, если
  соответствующее поле профиля не задано, без надуманных «пустых
  меток»), `response_format` (формулировка совместима с чанкингом
  `presentation/telegram/mapper.py::split_message` — не обещает доставку
  одним сообщением), `memory_placeholder`/`knowledge_placeholder`
  (комментарий про Этап 7/8 в тексте). Шаблоны читаются один раз в
  `__init__` (`dict[str, PromptTemplate]`), ошибки — `InfrastructureError`
  с понятным сообщением (не голый `OSError`/`KeyError`/
  `JSONDecodeError`). Добавлен `[tool.setuptools.package-data]` в
  `pyproject.toml` для `dekoder.infrastructure.prompts` — без этой
  записи `pip install .` (используется `Dockerfile`) молча не включил бы
  `templates/*.txt`/`manifest.json` в собранный wheel (это не
  Python-пакет — в `templates/` нет `__init__.py`), приложение упало бы
  внутри контейнера при первом обращении к `FileTemplateRepository`,
  хотя работало бы штатно при локальном запуске из исходников —
  проверено эмпирически (сборка wheel, инспекция содержимого архива).
  Никакой новой зависимости-шаблонизатора не добавлено (`string.Template`,
  stdlib) — см. §36 для подробностей.
* [x] S4-05 — `application/prompt/services/prompt_builder.py::
  DeterministicPromptBuilder` — единственная реализация `PromptBuilder`:
  рендерит секции 1/2/8 без пользовательских переменных, секцию 3 из
  ВСЕХ описательных полей активного профиля (не только
  `system_instruction`, ADR-4.7 — `preferred_model` намеренно не
  используется, выбор модели — Этап 10), секции 4/5 тем же кодовым
  путём для пустых (Sprint 4) и будущих непустых (Этапы 7/8) входных
  данных; строит `messages` из `context.dialogue_history` (role-mapping,
  переехавший из `ProcessUserMessage`); вызывает `TokenBudgetPolicy.
  enforce(...)` последним шагом. Проверка обязательных переменных шаблона
  — приватный метод `_substitute` этого же сервиса (не отдельный
  `PromptValidationService`, ADR-4.9) — поднимает `ApplicationError`,
  называющую и шаблон, и недостающие переменные. Тесты: порядок секций
  1,2,3,4,5,8 (не включает 6/7 — они в `messages`), пустые секции 4/5 не
  протекают в `system_prompt`, полный рендер профиля на синтетическом
  профиле с непустыми `forbidden_phrasing`/`response_length_hint`/
  `additional_constraints`, явная ошибка на отсутствующую переменную,
  детерминированность, `template_versions` заполнен — плюс интеграционный
  прогон на реальном `FileTemplateRepository` для всех 4 сид-профилей
  (`alembic/versions/27c4e9f2a103_seed_profile_catalog.py`), доказывающий,
  что собранный `system_prompt` видимо различается по профилю (ADR-4.7
  DoD) — см. §36 для подробностей.
* [x] S4-06 — `application/prompt/services/token_budget.py::
  estimate_size` — эвристика по количеству символов (не токенизатор),
  изолированная в отдельной функции, задокументированная как MVP-
  приближение (ADR-4.4). `shared/config.py::PromptSettings`
  (`env_prefix="PROMPT_"`, `token_budget: int = 12000`) — бюджет из
  `Settings`, не хардкод, по аналогии с `LLMSettings.temperature/
  max_tokens`. Полный алгоритм тиров `TokenBudgetPolicy` уже был
  реализован в S4-02 (ADR-4.5 явно помещает его в `domain/prompt/
  policies.py`) — эта задача добавляет конкретную эвристику + бюджет из
  `Settings`, которыми конфигурируется политика, и подтверждает (grep)
  ровно одну точку вызова `enforce()` во всём проекте
  (`application/prompt/services/prompt_builder.py`). Добавлен
  end-to-end тест (`test_token_budget.py`), прогоняющий
  `DeterministicPromptBuilder` с реальными сид-шаблонами и реальной
  эвристикой (не синтетическим `len`, как в S4-02) — подтверждает
  обрезание длинной истории по всему стеку Prompt Engine, а не только в
  изолированном юните политики — см. §36 для подробностей.
* [x] S4-07 — интеграция в `ProcessUserMessage`
  (ADR-4.1/4.6/4.7/4.8): `_save_user_message` (транзакция 1) возвращает
  `(conversation_id, profile: UserProfile)` вместо прежнего
  `(conversation_id, system_instruction: str)`; `execute()` после
  `_load_history` собирает `PromptContext(profile=profile,
  dialogue_history=history)`, вызывает `self._prompt_builder.build(context)`
  и строит `LLMRequest` практически без преобразований из
  `PromptBuildResult` — ни цикла role-mapping, ни склейки строк промпта
  в use case больше нет. Три короткие транзакции не реструктурированы
  (по-прежнему ровно 3 вызова `self._repositories()`, `PromptBuilder.
  build()` вызывается синхронно между транзакцией загрузки истории и
  вызовом LLM, ни разу не внутри открытой сессии). Новое trailing-поле
  `ProcessUserMessageResult.prompt_template_versions: Mapping[str, str]
  = {}` (по аналогии с `usage: TokenUsage | None = None`) заполняется
  из `PromptBuildResult.template_versions`; `presentation/telegram/
  handlers/messages.py` логирует те же данные через `shared.logging.
  get_logger` внутри уже установленного `bind_request_context`, до
  `clear_request_context()` в `finally`. Удалены `_DEFAULT_SYSTEM_PROMPT`
  и параметр конструктора `default_system_prompt` из `bootstrap/
  container.py`/`ProcessUserMessage` — база текста уже мигрировала в
  сид-шаблон `base_instruction` (S4-04) и рендерится безусловно как
  секция 1. Перед удалением проверено покрытие Sprint 2/3: один тест
  (`TestPersonalization::test_falls_back_to_default_system_prompt_when_
  profile_instruction_is_blank`) напрямую проверял это поведение —
  заменён узким эквивалентом
  (`test_base_instruction_present_even_when_profile_instruction_is_blank`),
  доказывающим тот же сценарий «пустой профиль» через новую, всегда
  присутствующую секцию 1, а не через отдельный fallback (ADR-4.7 явно
  фиксирует это как видимое, ожидаемое изменение поведения — собранный
  `system_prompt` теперь длиннее и структурированнее, чем в Sprint 3,
  даже когда доменные данные не изменились). `bootstrap/container.py`
  собирает и внедряет `FileTemplateRepository`/`TokenBudgetPolicy`/
  `DeterministicPromptBuilder`, бюджет — из `settings.prompt.
  token_budget`. Все прямые конструкторы `ProcessUserMessage` в
  существующих тестах (6 файлов: unit/integration/e2e) переведены на
  новый параметр `prompt_builder` через новый
  `tests/support/prompt_engine.py::make_test_prompt_builder()` (реальный
  `DeterministicPromptBuilder` + реальные сид-шаблоны, просторный
  бюджет по умолчанию — не fake); сравнения `request.system_prompt` по
  точному равенству заменены на проверку вхождения — собранный промпт
  теперь составная, более длинная строка, не `profile.system_instruction`
  как есть (тот же явно задокументированный ADR-4.7 эффект) — см. §36
  для подробностей.
* [x] S4-08 — финальная интеграция и E2E-проверка Sprint 4: полный
  аудит `bootstrap/container.py` (DI-сборка `FileTemplateRepository`/
  `TokenBudgetPolicy`/`DeterministicPromptBuilder`, бюджет из `Settings`)
  не выявил дефектов — вся сборка уже была корректно подключена в
  S4-07. В отличие от S2-11/S3-09 (каждая нашла и исправила один-два
  реальных интеграционных дефекта), полный аудит S4-08 не выявил ни
  одного нового интеграционного дефекта, требующего исправления —
  честный, а не подогнанный результат: Prompt Engine проектировался с
  самого начала с учётом ограничений, обнаруженных в предыдущих
  спринтах (единственная фабрика репозиториев, синхронный `PromptBuilder`
  без I/O, `package-data` для сид-шаблонов уже добавлен в S4-04 и
  проверен сборкой wheel заранее). Добавлен
  `tests/e2e/test_prompt_engine_scenario.py` — два обязательных
  сценария поверх РЕАЛЬНОГО `telegram.ext.Application` + временной
  SQLite (тот же харнесс, что и `test_conversation_persistence_scenario.py`/
  `test_profile_scenario.py`): (1) собранный системный промпт реально
  содержит секцию активного профиля, не пуст; (2) диалог из 25
  предыдущих сообщений с заведомо малым `TokenBudgetPolicy`-бюджетом
  (1500 символов) — реально обрезается (LLM получает меньше 51
  сообщений, последнее — текущий запрос, неприкосновенный), ответ
  пользователю всё равно приходит нормально через `TextMessageHandler`.
  Видимая разница промпта между двумя профилями через `/profile`
  (переключение) уже доказана `tests/e2e/test_profile_scenario.py`
  (обновлена в S4-07 под составной `system_prompt`) — не дублировалась
  здесь. Собран реальный Docker-образ (`docker build`), запущен
  контейнер (`docker run` с временным volume и переопределённым
  `TELEGRAM_WEBHOOK_SECRET` для теста) — `/health` отвечает `200`;
  `alembic upgrade head` → `downgrade -1` → `upgrade head` внутри
  контейнера проходит без ошибок (сид-каталог восстанавливается: 4
  профиля, ровно 1 `is_default`); отдельно подтверждено, что
  `FileTemplateRepository()` внутри контейнера реально находит и
  загружает все 6 сид-шаблонов (проверка `package-data`-фикса из S4-04
  на настоящем собранном образе, не только на локальном wheel);
  `build_container()` внутри контейнера собирает `ProcessUserMessage` с
  `prompt_builder._budget == 12000` (значение из `.env`/`Settings`, не
  хардкод). Полный набор тестов (496), Ruff, Ruff format, MyPy проходят.
  `README.md` обновлён: диаграмма основного сценария показывает
  `PromptContext -> PromptBuilder -> PromptBuildResult`, дерево
  каталогов включает `domain/prompt`/`application/prompt`/
  `infrastructure/prompts`, таблица переменных окружения — `PromptSettings`/
  `PROMPT_TOKEN_BUDGET`, раздел «Тесты» — `test_prompt_engine_scenario.py`,
  абзац про мёртвый v2.0-скелет — про удаление логгера/`prompt_engine` в
  S4-01. Новая бизнес-функциональность не добавлена — Sprint 4
  (S4-01…S4-08) полностью завершён, 496 тестов, ruff/ruff format/mypy
  проходят — см. §36 для подробностей.

## Текущий спринт (обновление 4)

**Спринт 5: долговременная память — контролируемое сохранение,
просмотр, удаление подтверждённых фактов пользователя, влияющих на
ответы ассистента через секцию 4 Prompt Engine — завершён (S5-01…S5-08).**

Цель и полный состав спринта — внешняя архитектурная спецификация
`backlog_5.md` (12 ADR, не входит в этот репозиторий) и §33/§15 ниже.
Прогресс по задачам:

* [x] S5-01 — удаление мёртвого v2.0-скелета памяти:
  `application/memory/*` (порт `MemoryRepository` со старой формой
  `record_message`/`stage_fact_draft`/`confirm_fact_draft`/
  `forget_fact`, use cases `RecordDialogueMessageUseCase` и др., все
  `raise NotImplementedError`), `domain/memory/*` (`DialogueEntry`,
  `MemoryFact`, `MemoryFactDraft` — простые `@dataclass`, без
  `frozen`/`slots`/валидации), `infrastructure/persistence/
  sqlite_memory_repository.py`, `application/ai_core/internal_services/
  memory_collector.py` — та же логика, что ADR-4.10 (Sprint 4, S4-01):
  правдоподобно выглядящий «модуль памяти» ровно в момент, когда строился
  настоящий (ADR-5.1) — его форма (диалог+черновик факта) структурно не
  совпадала со спецификацией Этапа 7 (`MemoryRecord`/`MemoryCategory`/
  `MemoryStatus`/`MemorySource`/`MemoryConfidence`), это артефакт другой,
  отменённой модели предметной области, не частичная реализация. Точечно
  зачищен импорт/поле `MemoryRepository`/`Container.memory_repository` в
  `composition/container.py`. Отклонение от буквального текста задачи
  (которая ограничивала точечную зачистку только `composition/
  container.py`): сама доменная модель, удаляемая этой задачей,
  транзитивно импортировалась ещё из четырёх файлов, не входящих в узел
  памяти (`shared/application/execution_context.py`,
  `application/ai_core/internal_services/execution_context_builder.py`,
  `application/ai_core/use_cases/{generate_content,
  answer_knowledge_question,route_command}.py`) — без точечной зачистки
  dangling-импортов и там дерево не проходило бы `mypy src` целиком.
  Разрешено тем же приёмом, что уже установлен S4-01 для идентичной
  ситуации (Logger/PromptAssembler/PromptBuilder): убраны только
  импорт и ставший недостижимым параметр/метод, поведение
  (`raise NotImplementedError`) не изменилось. `shared/domain/
  identifiers.py` не тронут (используется остальным v2.0-скелетом, его
  судьба — отдельная будущая задача, ADR-5.1) — единственный оставшийся
  grep-хит (`DialogueEntryId`) — ожидаемое, задокументированное
  исключение. Остальной v2.0-скелет (`admin`, `rag`, `session`, `skills`,
  `model_catalog`, `knowledge_base`, `model_gateway`,
  `infrastructure/vector_storage`, `interfaces/`, `composition/` за
  пределами точечной правки) не тронут — см. §36 для подробностей.
* [x] S5-02 — доменный слой памяти (`domain/memory/{entities,
  value_objects}.py`), стиль `domain/profile/entities.py::UserProfile`:
  `MemoryRecord` (`frozen=True, slots=True`, `__post_init__`: непустой
  `text`, `updated_at >= created_at`) с полями `id`/`user_id: UUID`
  (плоский тип, без обёртки — ADR-5.2, `shared/domain/identifiers.py` не
  импортируется), `text`, `category`, `source`, `status`, `confidence`,
  `is_sensitive: bool`, `expires_at: datetime | None`, `updated_by: str`,
  `created_at`/`updated_at`. Четыре plain `Enum` (не `str, Enum` — стиль
  `ProfileStatus`): `MemoryCategory` (`PERSONAL`/`PREFERENCE`/`FACT`/
  `OTHER`), `MemorySource` (`USER_EXPLICIT`/`ADMIN`/`INFERRED` —
  последние два зарезервированы, ничего в Sprint 5 их не производит),
  `MemoryStatus` (`PENDING`/`CONFIRMED`/`REJECTED`), `MemoryConfidence`
  (`LOW`/`MEDIUM`/`HIGH`). Ноль I/O-зависимостей. Юнит-тесты — валидация
  + типы полей `id`/`user_id` + подтверждение plain-`Enum` стиля — см.
  §36 для подробностей.
* [x] S5-03/S5-04 — порт `MemoryRepository` (`application/memory/
  ports.py`, `@runtime_checkable`, стиль `ProfileRepository`: `save`,
  `find_relevant(user_id, limit)`, `list_confirmed_by_user`, `get_by_id`,
  `update_status`, `delete(record_id, user_id)`), встроен в
  `ConversationRepositories.memory` тем же приёмом, что `profiles`
  (ADR-3.3/5.5) — без второй фабрики репозиториев; `MemoryRecordORM` +
  `SQLAlchemyMemoryRepository` (`infrastructure/persistence/
  memory_record_orm.py`/`memory_repository.py`) — `category`/`source`/
  `status`/`confidence` как `String`+`CheckConstraint` (стиль
  `ProfileORM.status`); `find_relevant` сортирует `confidence DESC,
  created_at DESC` через явный `CASE`-ранг (`_CONFIDENCE_RANK`) — простая
  лексикографическая сортировка строк `'low'/'medium'/'high'` НЕ ставит
  `'high'` первым (`'medium' > 'low' > 'high'` по алфавиту), обнаружено
  при проектировании запроса, не задним числом; `delete` изолирует
  пользователей на уровне SQL (`WHERE id = :id AND user_id = :user_id`).
  Схемная Alembic-миграция `161899ea36c0_create_memory_records.py` —
  таблица `memory_records` + индекс `(user_id, status)`, без сид-данных
  (ADR-5.7, в отличие от `profiles`). Отклонение от буквального текста
  задач: `backlog_5_tasks.md` разносит порт (S5-03, включая проводку
  `bootstrap/repositories.py`) и адаптер (S5-04) по разным
  коммитам/задачам — но `ConversationRepositories.memory`, сделанное
  обязательным полем без значения по умолчанию (тем же стилем, что
  `profiles`), требует реальной реализации уже в `bootstrap/
  repositories.py::build_conversation_repositories_factory`, иначе дерево
  не собирается (`mypy`); реализация объединена в один коммит — тот же
  прецедент, которым Sprint 3 уже разрешил идентичную коллизию для
  `ProfileRepository` (задача S3-05, «add ProfileRepository port,
  SQLAlchemy adapter, wire into ConversationRepositories» — одним
  коммитом). Попутно исправлены два теста миграций (`test_migrations.py`),
  использовавших относительный `downgrade(config, "-1")` в расчёте на
  то, что сид-миграция профилей (`27c4e9f2a103`) — head; после S5-04 head
  — `161899ea36c0`, тесты переведены на явный целевой ревижн
  (`"14bf7e3ae815"`), устойчивый к будущим миграциям поверх — см. §36 для
  подробностей.
* [x] S5-05 — use cases памяти (`application/memory/use_cases/*`):
  `CreateMemoryRecordUseCase` (принимает `status`/`source` параметром, не
  хардкодит `CONFIRMED` внутри себя — ADR-5.9; создаёт пользователя
  автоматически, `get_or_create_by_telegram_user_id`, тем же приёмом, что
  `ProcessUserMessage` — `/remember` может быть первым действием
  пользователя), `ConfirmMemoryRecordUseCase`/`RejectMemoryRecordUseCase`
  (полноценно реализованы, не заглушки — задел на будущий подтверждаемый
  сценарий, без вызывающего Telegram-сценария в Sprint 5, тот же
  прецедент, что тиры 4/5 `TokenBudgetPolicy`, ADR-4.5/S4-06),
  `ListMemoryRecordsUseCase` (только `CONFIRMED`, не создаёт
  пользователя), `DeleteMemoryRecordUseCase` (идемпотентна — прецедент
  `MessageRepository.clear`, не полагается на Telegram-слой как
  единственную защиту владения). `UpdateMemoryRecord` сознательно не
  реализован — задокументировано в докстринге `application/memory/
  use_cases/__init__.py` (нет вызывающего сценария без админ-интерфейса,
  Этап 10). Каждый use case, меняющий память (create/confirm/reject/
  delete), логирует через `shared.logging.get_logger` — без `record.text`
  при `is_sensitive=True` (ADR-5.8/5.12); `ListMemoryRecordsUseCase` не
  логирует — read-only, ADR-5.12 требует журналирования только изменений.
  Тесты перехватывают реальный JSON-вывод `shared/logging.py` (`capsys`,
  как `tests/unit/shared/test_logging.py`), подтверждают отсутствие
  текста факта для чувствительных записей и присутствие — для обычных
  (не только отрицательная проверка) — см. §36 для подробностей.
* [x] S5-06 — интеграция в `ProcessUserMessage` (ADR-5.4/5.6/5.11):
  `_save_user_message` (транзакция 1) сразу после `repositories.profiles.
  get_active_profile(user.id)` читает `repositories.memory.find_relevant(
  user.id, limit=self._max_relevant_memory)` — тем же приёмом, тем же
  вызовом `self._repositories()`, без новой транзакции; возвращает
  `(conversation_id, profile, memory_records)`; `execute()` собирает
  `PromptContext(profile=profile, dialogue_history=history,
  confirmed_memory_facts=[r.text for r in memory_records])`. Отдельный
  use-case класс `FindRelevantMemory` не создан — порт вызывается
  напрямую (ADR-5.4, по прецеденту `get_active_profile`/ADR-4.9).
  `shared/config.py::MemorySettings` (`env_prefix="MEMORY_"`,
  `max_relevant_records: int = Field(default=5, gt=0)`, стиль
  `PromptSettings.token_budget`) — лимит из `Settings`, не хардкод.
  `git diff --stat feature/sprint-4..HEAD -- src/dekoder/domain/prompt
  src/dekoder/application/prompt src/dekoder/infrastructure/prompts` —
  пусто: ноль изменений в Prompt Engine (ADR-5.11), подтверждено
  командой, не на слово. Интеграционный тест с РЕАЛЬНЫМ `PromptBuilder`
  (не fake) подтверждает: собранный `system_prompt` содержит текст
  подтверждённого факта; `PENDING`/истёкшие записи исключены;
  `find_relevant` вызывается в пределах уже существующих 3 вызовов
  `self._repositories()` за `execute()` (не увеличилось относительно
  Sprint 4) — см. §36 для подробностей.
* [x] S5-07 — Telegram `/remember`/`/memory`
  (`presentation/telegram/handlers/memory.py`): `RememberCommandHandler`
  (текст после команды — `maxsplit=1`, сохраняет внутренние
  пробелы/переносы, в отличие от `context.args`; пустой текст — понятная
  ошибка, не падение; `status=CONFIRMED, source=USER_EXPLICIT` — явно, в
  `mapper.py::to_create_memory_record_command`, не хардкод внутри use
  case'а, ADR-5.9), `MemoryListCommandHandler` (`InlineKeyboardMarkup`, по
  кнопке 🗑 на запись; пустой список — дружелюбное сообщение, не пустая
  клавиатура), `MemoryDeleteCallbackHandler` (`telegram_user_id` из
  `update.callback_query.from_user`, НЕ `update.effective_user` — тот же
  принцип, что `ProfileSelectionCallbackHandler`/`to_select_profile_command`,
  ADR-5.10; `query.answer()` + `query.edit_message_text(...)` с
  обновлённым списком). Нет команды `/forget` (ADR-5.10) — удаление
  только через inline-кнопку. `bot.py::register_memory_handlers` +
  `telegram_main.py` регистрируют три хендлера тем же способом, что и
  `/profile` (внутри `post_init`, после DB-зависимого контейнера);
  `bootstrap/container.py` собирает `CreateMemoryRecordUseCase`/
  `ListMemoryRecordsUseCase`/`DeleteMemoryRecordUseCase` — не
  `ConfirmMemoryRecordUseCase`/`RejectMemoryRecordUseCase` (нет
  Telegram-вызывающего сценария в Sprint 5, ADR-5.9, контейнер не
  собирает объекты, которые некому передать). E2E-тест
  (`tests/e2e/test_memory_scenario.py`, реальный `telegram.ext.
  Application` + реальная временная SQLite): `/remember` → `/memory`
  показывает факт с кнопкой; пустой текст/пустой список; удаление через
  callback; **пользователь B не может удалить запись пользователя A даже
  подделав `callback_data` с чужим id** (ADR-5.10 AC) — получает свой
  пустой список, не тихий успех; `/forget` не зарегистрирован — см. §36
  для подробностей.
* [x] S5-08 — финальная интеграция и E2E-проверка Sprint 5: полный аудит
  `bootstrap/container.py` (DI-сборка `SQLAlchemyMemoryRepository`,
  `MemorySettings`, трёх use case'ов памяти) не выявил дефектов — вся
  сборка уже была корректно подключена задачами S5-03…S5-07. Как и
  S4-08 (и в отличие от S2-11/S3-09, каждая из которых нашла и точечно
  исправила один-два реальных интеграционных дефекта), полный аудит
  S5-08 не выявил ни одного нового интеграционного дефекта, требующего
  исправления — честный результат: узкие границы транзакций/DI,
  установленные Sprint 2-4, оказалось достаточно просто расширить
  дополнительным полем/портом без структурных сюрпризов. Добавлен
  `tests/e2e/test_memory_prompt_scenario.py` — «Сценарий 4» §18.4 «Плана
  реализации.md» буквально: `/remember` → `/new` → обычное сообщение →
  собранный `system_prompt` (эквивалент `PromptBuildResult.system_prompt`
  — `LLMRequest.system_prompt=build_result.system_prompt` без
  преобразований, ADR-4.1) реально содержит сохранённый факт; факт
  пользователя A никогда не появляется в промпте пользователя B; `/clear`
  и `/new` не удаляют `memory_records` (факт по-прежнему в `/memory`
  после очистки истории/начала нового диалога — §13.5 «Плана
  реализации.md»); редакция чувствительных записей в логах
  эмпирически подтверждена и поверх РЕАЛЬНОГО `SQLAlchemyMemoryRepository`
  (не только fake-репозитория из S5-05) — создание/удаление записи с
  `is_sensitive=True` не публикует `record.text` в JSON-вывод. Собран
  реальный Docker-образ (`docker compose build`), запущен контейнер
  (`docker compose up -d api`) — `/health` отвечает `200`; `alembic
  upgrade head` → `downgrade -1` → `upgrade head` внутри контейнера
  проходит без ошибок, схема `memory_records` (все `CHECK`-ограничения +
  FK + индекс `(user_id, status)`) подтверждена прямым запросом к
  `sqlite_master` внутри контейнера; `Settings().memory.
  max_relevant_records == 5` и полный состав полей `ApplicationContainer`
  (включая три use case'а памяти) подтверждены реальным импортом внутри
  собранного образа, не только локально. Полный набор тестов (565),
  Ruff, Ruff format, MyPy проходят. `README.md` обновлён: диаграмма
  основного сценария показывает память в цепочке `ProcessUserMessage`,
  дерево каталогов включает `domain/memory`/`application/memory`/новые
  файлы `infrastructure/persistence/`/`presentation/telegram/handlers/
  memory.py`, раздел «База данных и миграции» — четвёртая ревизия
  (`161899ea36c0`, без сид-данных), таблица переменных окружения —
  `MemorySettings`/`MEMORY_MAX_RELEVANT_RECORDS`, раздел «Тесты» —
  `test_memory_scenario.py`/`test_memory_prompt_scenario.py`, абзац про
  мёртвый v2.0-скелет — про удаление узла памяти в S5-01. `.env.example`
  дополнен разделом `MemorySettings`. Новая бизнес-функциональность не
  добавлена — Sprint 5 (S5-01…S5-08) полностью завершён, 565 тестов,
  ruff/ruff format/mypy проходят — см. §36 для подробностей.

**Примечание об отсутствующей записи Sprint 6.** Между этой записью и
следующей нет отдельной записи «Спринт 6» — процессное упущение
предыдущей сессии, не потеря функциональности: Sprint 6 (Этап 8, база
знаний и RAG, S6-01…S6-11) реально завершён и работает в кодовой базе
(`domain/knowledge`, `application/knowledge`, `infrastructure/{documents,
embeddings,qdrant}`, `SemanticSearchService`, интеграция в
`ProcessUserMessage`, `scripts/index_document.py`), что и подтверждено
задачей S7-08 (полный `pytest`/Docker-аудит ниже видит эту функциональность
работающей без регрессий) — коротко, по коммитам ветки `feature/sprint-6`:
S6-01 — удаление мёртвого v2.0-скелета `knowledge_base`/`rag`/`admin`
узла базы знаний; S6-02 — `QdrantSettings`/`KnowledgeSettings`,
Qdrant-инфраструктура; S6-03/S6-04 — доменный слой знаний, порты,
`KnowledgeDocumentRepository`; S6-05 — парсеры документов (txt/markdown/
docx/pdf), chunking, `OpenAiEmbeddingProvider`, файловое хранилище;
S6-06 — `IndexKnowledgeDocumentUseCase`/`DeleteKnowledgeDocumentUseCase`;
S6-07 — `SemanticSearchService`; S6-08 — интеграция RAG в
`ProcessUserMessage` (`_search_knowledge`, вне DB-транзакций, сбой не
обрушивает ответ); S6-09 — `scripts/index_document.py`; S6-10 — добивка
покрытия тестами; S6-11 — финальная интеграция, Docker/Qdrant-фиксы. Эта
запись восстановлена задним числом по заголовкам коммитов при работе над
Sprint 7 — не заменяет полноценную запись §32, если она когда-либо
понадобится в исходной глубине (ADR/девиации Sprint 6 нужно поднимать из
`backlog_6.md`/истории коммитов отдельно).

## Текущий спринт (обновление 5)

**Спринт 7: выбор AI-модели пользователем — статичный файловый каталог
моделей, персональный выбор через Telegram-команду `/model`, интеграция
в `ProcessUserMessage` с молчаливым логируемым откатом при недоступности
выбранной модели — завершён (S7-01…S7-08).**

Цель и полный состав спринта — внешняя архитектурная спецификация
`backlog_7.md` (9 ADR, не входит в этот репозиторий) и §33 ниже.
Реализует Этап 9 «Плана реализации.md». Прогресс по задачам:

* [x] S7-01 — удаление мёртвого v2.0-скелета каталога моделей:
  `domain/model_catalog/model_definition.py` (`ModelDefinition` — плоский
  dataclass, `ModelAvailabilityStatus`), `application/model_catalog/*`
  (`ports.py::ModelCatalogRepository` со старой формой `get`/`list_all`/
  `list_compatible(skill_id, generation_type)`, `queries.py`,
  `use_cases/get_available_models.py` — `raise NotImplementedError`),
  `application/model_gateway/ports.py::ModelGateway`,
  `infrastructure/model_gateway/{llm/openai_llm_adapter.py,
  llm/yandexgpt_llm_adapter.py,image_model/__init__.py}`,
  `infrastructure/persistence/sqlite_model_catalog_repository.py` — та же
  логика, что ADR-4.10/5.1/6.x: структурно другая, отменённая модель
  предметной области (плоский `ModelDefinition`, не
  `AIModel`/`AIProvider`/`ModelCapability`/`ModelAvailability`/
  `GenerationSettings`), использующая мёртвый `ModelId` из
  `shared/domain/identifiers.py`, а не живой `domain/conversation/
  value_objects.ModelId`; ноль тестового покрытия, ноль реальных
  импортов из `bootstrap`/`presentation`. Точечно зачищен импорт/поле
  `ModelCatalogRepository`/`ModelGateway` в `composition/container.py`.
  Отклонение от буквального текста задачи (та ограничивала точечную
  зачистку только `composition/container.py`) — тем же прецедентом, что
  и S5-01/S6-01: dangling-импорты удаляемого узла транзитивно
  затрагивали ещё четыре файла мёртвого `application/ai_core/*`
  (`internal_services/{model_selector,response_formatter}.py`,
  `use_cases/{generate_content,route_command}.py`) — без точечной
  зачистки там `mypy src` не проходил бы целиком;
  `model_selector.py`/`response_formatter.py` (целиком построенные
  вокруг удаляемых типов) удалены полностью — тот же приём, что
  `knowledge_collector.py` в S6-01; `generate_content.py`/
  `route_command.py` лишились только относящихся к каталогу
  параметров/методов, поведение (`raise NotImplementedError`) не
  изменилось. Остальной v2.0-скелет (`admin`, `rag`, `session`, `skills`,
  `knowledge_base`, `interfaces/`, `shared/domain/identifiers.py`,
  `composition/` за пределами точечной правки) и живой `domain/user`/
  `application/user` не тронуты — см. §36 для подробностей.
* [x] S7-02 — доменный слой каталога моделей
  (`domain/model_catalog/{entities,enums,value_objects}.py`), стиль
  `domain/profile/entities.py::UserProfile`: `AIModel` (`frozen=True,
  slots=True`, `__post_init__`: непустой `display_name`,
  `context_window > 0`) с полями `model_id: ModelId` (импорт
  исключительно из `domain.conversation.value_objects` — ADR-7.2, не
  создан третий тип `ModelId`), `display_name`, `provider`,
  `context_window`, `capabilities: frozenset[ModelCapability]`,
  `price_tier`, `availability`, `recommended_for: tuple[str, ...]`,
  `default_generation_settings: GenerationSettings`; никакого отдельного
  поля «внешний идентификатор»/`technical_id` (ADR-7.3: `model_id.value`
  — одновременно и каталожный ключ, и значение для
  `LLMRequest.model_id`, OpenRouter уже сам федерирует поставщиков).
  Четыре plain `Enum` (не `str, Enum` — стиль `ProfileStatus`):
  `AIProvider` (`OPENAI`/`ANTHROPIC`/`GOOGLE`/`YANDEX`/`META`/`OTHER`),
  `ModelCapability` (`TEXT`/`VISION`/`FUNCTION_CALLING`),
  `ModelAvailability` (`AVAILABLE`/`UNAVAILABLE`), `ModelPriceTier`
  (`LOW`/`MEDIUM`/`HIGH`). `GenerationSettings` (`frozen=True,
  slots=True`, `__post_init__`: `0.0 <= temperature <= 2.0`,
  `max_tokens > 0`) — единственное поле каталога, реально влияющее на
  генерацию (не информационное, ADR-7.3/7.7). Ноль I/O-зависимостей.
  Юнит-тесты — валидация + подтверждение plain-`Enum` стиля + отсутствие
  поля «внешний идентификатор» — см. §36 для подробностей.
* [x] S7-03 — порт `ModelCatalogRepository` (`application/model_catalog/
  ports.py`, `Protocol`, синхронные `get`/`list_all` — каталог грузится в
  память один раз, не на каждый вызов) и файловая реализация
  `ConfigModelCatalogRepository` (`infrastructure/model_catalog/
  config_repository.py`), прямой прецедент `FileTemplateRepository`
  (Sprint 4, ADR-4.2): парсит `infrastructure/model_catalog/catalog.json`
  через pydantic wire-схему (`infrastructure/model_catalog/schemas.py`,
  стиль `infrastructure/llm/schemas.py`) → маппинг в доменный `AIModel`;
  ошибка при отсутствующем/повреждённом файле или невалидной записи —
  `InfrastructureError`, поднимается при построении (fail-fast), не при
  первом `get()`/`list_all()`. Сид-каталог — 6 реальных моделей
  OpenRouter, 4 поставщика (openai/anthropic/google/meta), одна модель
  (`anthropic/claude-3-haiku`) намеренно `UNAVAILABLE` — для содержательной
  проверки пометки «(недоступна)» в `/model` и отката в `ProcessUserMessage`
  без необходимости отдельного fixture-каталога в part of e2e-тестов.
  `shared/config.py::ModelCatalogSettings` (`env_prefix="MODEL_CATALOG_"`,
  `catalog_path: Path`, значение по умолчанию вычисляется относительно
  расположения `shared/config.py`, не импортом `infrastructure/` — не
  создаёт зависимости `shared/` от `infrastructure/`) добавлена в
  `Settings` тем же приёмом, что `KnowledgeSettings`.
  `pyproject.toml::[tool.setuptools.package-data]` дополнен записью для
  `infrastructure/model_catalog/catalog.json` — тот же класс правки, что
  и сид-шаблоны Prompt Engine (S4-04): без неё `pip install .`
  (используется в `Dockerfile`) собрал бы пакет без `catalog.json`.
  Юнит-тесты на изолированном `tmp_path`-каталоге (не боевом
  `catalog.json`) + отдельные тесты на реальный сид — см. §36 для
  подробностей.
* [x] S7-04 — персональный выбор модели: `ModelSelection`
  (`domain/model_catalog/entities.py`, `frozen=True, slots=True`:
  `user_id: UUID`, `model_id: ModelId`, `selected_at: datetime`) и порт
  `ModelSelectionRepository` (`application/model_catalog/ports.py`,
  `get_selected(user_id) -> ModelId | None`/`select(user_id, model_id) ->
  None`) — `SQLAlchemyModelSelectionRepository` +
  `UserActiveModelORM`/таблица `user_active_models`
  (`infrastructure/persistence/{sqlalchemy_model_selection_repository.py,
  user_active_model_orm.py}`) — прямой прецедент
  `SQLAlchemyProfileRepository.select_profile`/`user_active_profiles`
  (ADR-3.1): `user_id` одновременно первичный и внешний ключ,
  `select()` — атомарный `INSERT ... ON CONFLICT(user_id) DO UPDATE`
  upsert, свой `commit()` (не «сначала SELECT, потом INSERT» без защиты
  от гонки); `model_id` — обычная строка, без FK на каталог (каталог
  статичный файловый, ADR-7.4, ссылочную целостность обеспечивать
  нечем — проверка «модель существует и доступна» на уровне
  `SelectModel`, не БД). Схемная Alembic-миграция
  `ed5701d2f683_create_user_active_models.py` (сгенерирована `alembic
  revision --autogenerate`, без сид-данных, как `memory_records`/
  `knowledge_documents`), проверена локально `upgrade head → downgrade
  -1 → upgrade head`. `ConversationRepositories.model_selection` —
  новое поле, встроено тем же приёмом, что `profiles`/`memory`
  (ADR-3.3/5.5) — никакой второй фабрики репозиториев (ADR-7.5).
  Каждая существующая точка прямой сборки `ConversationRepositories(...)`
  в тестах (`tests/support/fake_conversation_repositories.py`,
  `tests/unit/application/test_process_user_message.py`,
  `tests/e2e/test_conversation_persistence_scenario.py`) обновлена под
  новое обязательное поле — тот же прецедент, что и добавление
  `profiles`/`memory` в Sprint 3/5. Интеграционные тесты — upsert
  (повторный выбор заменяет, не дублирует строку), изоляция между
  пользователями, `get_selected` без выбора → `None` — см. §36 для
  подробностей.
* [x] S7-05 — use cases каталога моделей (`application/model_catalog/
  use_cases/{list_models,get_selected_model,select_model}.py`):
  `ListAvailableModels` (композиция `ModelCatalogRepository.list_all()` +
  `ModelSelectionRepository.get_selected(user_id)`, не создаёт
  пользователя автоматически — просмотр каталога не требует
  предварительного `User`), `GetSelectedModel` (`model is None`, если
  пользователь неизвестен, выбор не сделан, или выбор указывает на
  `model_id`, которого больше нет в каталоге — устойчивость к изменению
  каталога после того, как выбор был сделан), `SelectModel` (проверяет
  наличие в каталоге и `availability = AVAILABLE`, при нарушении —
  `ApplicationError` с `code = MODEL_NOT_FOUND`/`MODEL_UNAVAILABLE`, ДО
  входа в транзакцию — `ModelSelectionRepository.select` не вызывается
  ни разу; при успехе создаёт пользователя автоматически, как
  `CreateMemoryRecord` — запись в `user_active_models` требует реального
  `user_id`). `ValidateModelAvailability` из §15.4 не выделен в отдельный
  use-case класс (ADR-7.7) — проверка инкапсулирована прямо в
  `SelectModel`. Отклонение от обычного для проекта паттерна
  «status-enum результата» (`SelectProfileStatus` и т.п.): по прямому
  требованию `backlog_7_tasks.md` S7-05 отказ `SelectModel` — «доменная
  ошибка, не молчаливый no-op», не статус-результат. Юнит-тесты с
  fake-репозиториями (`tests/support/fake_model_catalog.py`) — оба
  случая отказа `SelectModel`, устойчивость `GetSelectedModel` к
  устаревшему выбору, пометка активной модели `ListAvailableModels` —
  см. §36 для подробностей.
* [x] S7-06 — интеграция в `ProcessUserMessage` (ADR-7.7/7.8):
  `_save_user_message` (транзакция 1) дополнительно разрешает модель
  через новый `_resolve_model_id` по приоритету `command.model_id`
  (явный override, каталог не проверяется) → `repositories.
  model_selection.get_selected(user.id)` (тем же вызовом
  `self._repositories()`, что и `profiles`/`memory`) →
  `self._default_model`; кандидат шагов 2/3 проверяется через новый
  конструкторный параметр `model_catalog: ModelCatalogRepository`
  (внедрён отдельно, как `knowledge_search`, не через
  `ConversationRepositoriesFactory` — ADR-7.4) — `None`/`UNAVAILABLE` →
  тихий откат на `self._default_model` с `logger.warning(
  requested_model_id, fallback_model_id, user_id)`.
  `_resolve_generation_settings` берёт `temperature`/`max_tokens` из
  `default_generation_settings` разрешённой (после отката, если он
  случился) модели, если она есть в каталоге — иначе прежние
  `self._temperature`/`self._max_tokens`. `ValidateModelAvailability` не
  выделена в отдельный класс — та же логика, что и S7-05. `git diff
  --stat feature/sprint-6..HEAD -- src/dekoder/domain/prompt
  src/dekoder/application/prompt src/dekoder/infrastructure/prompts` —
  пусто: ноль изменений в Prompt Engine (ADR-7.8), подтверждено
  командой. `bootstrap/container.py` собирает
  `ConfigModelCatalogRepository` из `settings.model_catalog.catalog_path`
  и внедряет как `model_catalog`. Каждая существующая точка сборки
  `ProcessUserMessage(...)` в тестах (7 файлов —
  `tests/unit/application/test_process_user_message.py`,
  `tests/unit/presentation/telegram/test_messages_handler.py`, пять
  `tests/e2e/*_scenario.py`, `tests/integration/
  test_process_user_message_persistence.py`) получила `model_catalog`
  через новый `tests/support/fake_model_catalog.py::default_test_catalog()`
  helper, заполненный ТЕМИ ЖЕ `model_id`/`temperature`/`max_tokens`, что
  уже были захардкожены в каждом тесте — наблюдаемое поведение всех
  Sprint 2-6 тестов не изменилось ни на бит. Четыре целевых теста ADR-7.7
  (персональный выбор применяется; explicit override побеждает и не
  проверяется каталогом; недоступный персональный выбор → откат на
  умолчание с проверкой полей лога; устаревшая/удалённая из каталога
  модель тоже откатывается) — см. §36 для подробностей.
* [x] S7-07 — Telegram `/model`
  (`presentation/telegram/handlers/model.py`): `ModelCommandHandler`
  (вызывает `GetSelectedModel` — единственный вызывающий код по ADR-7.7,
  для строки «Текущая модель: …» — и `ListAvailableModels` для самой
  клавиатуры; в отличие от `ProfileCommandHandler` НЕ гейтится на «нет
  предыдущего взаимодействия» — просмотр каталога не требует
  существования `User`, ADR-7.9), `ModelSelectionCallbackHandler`
  (`callback_data = f"model:{model_id.value}"`, парсинг —
  `_parse_model_callback_data`, тот же `str.startswith`-паттерн, что
  `profile.py`; отказ `SelectModel` — `query.answer(error.user_message,
  show_alert=True)`, БЕЗ `edit_message_text` — список не портится,
  ADR-7.9 «список не портится»; успех — `edit_message_text` с
  подтверждением И обновлённой клавиатурой, в отличие от `profile.py`,
  который заменяет текст без клавиатуры; ровно один `query.answer(...)`
  на путь выполнения — черновик с безусловным `answer()` вначале плюс
  ещё одним `answer(..., show_alert=True)` в ветке ошибки был найден и
  исправлен при написании тестов, Telegram не принимает двойной ответ на
  один callback). Клавиатура помечает активную модель текстовым
  суффиксом «(текущая)» и недоступную — «(недоступна)» (кнопка всё ещё
  показывается, `SelectModel` отклонит попытку выбрать). Префикс
  `model:` дизъюнктен с `profile:`/`memory_delete:`. `telegram_user_id`
  для callback — из `update.callback_query.from_user`
  (`mapper.py::to_select_model_command`), не `update.effective_user`
  (ADR-7.9); значение переиспользуется напрямую для обновления списка
  после выбора, не выводится второй раз через `Update`.
  `bootstrap/container.py` собирает `list_available_models`/
  `get_selected_model`/`select_model` поверх той же `repositories_factory`
  и того же `model_catalog`, что и `ProcessUserMessage`;
  `bot.py::register_model_handlers`/`telegram_main.py` регистрируют оба
  хендлера внутри `post_init`, после `/remember`/`/memory`. Юнит-тесты
  (`tests/unit/presentation/telegram/test_model_handler.py`, 19 тестов) —
  известный/неизвестный пользователь, пометка активной/недоступной
  модели, форма `callback_data`, успешный выбор с обновлением клавиатуры,
  оба случая отказа `SelectModel` (alert, сообщение не редактируется,
  выбор не меняется), некорректный `callback_data`,
  `callback_query.from_user` vs `effective_user`, обработка
  `DekoderError`/непредвиденных ошибок на обоих хендлерах, отсутствие
  прямого импорта SQLAlchemy/`infrastructure/` в presentation-слое — см.
  §36 для подробностей.
* [x] S7-08 — финальная интеграция и E2E-проверка Sprint 7: полный аудит
  `bootstrap/container.py` не выявил дефектов — DI каталога моделей и
  персонального выбора (S7-06/S7-07) уже были корректно подключены.
  Добавлен `tests/e2e/test_model_selection_scenario.py` (7 тестов, реальный
  `telegram.ext.Application` + реальная временная SQLite + реальный
  `ConfigModelCatalogRepository()` на боевом `catalog.json`, единственная
  подмена — `FakeLLMProvider`): выбор модели через `/model` реально
  меняет `LLMRequest.model_id`/`temperature`/`max_tokens` (сверено с
  `default_generation_settings` боевой модели `anthropic/claude-3.5-sonnet`,
  отличающимися от `Settings.llm`, переданных конструктору, — не
  случайное совпадение); откат при недоступности (персональный выбор
  указывает на боевую `anthropic/claude-3-haiku`, `UNAVAILABLE` в
  сид-каталоге — записан напрямую через
  `SQLAlchemyModelSelectionRepository.select()`, в обход `SelectModel`,
  симулируя «каталог обновился уже после выбора») — ответ всё равно
  генерируется моделью по умолчанию, лог отката (`model_selection_fallback`,
  `level=warning`) эмпирически подтверждён через `capsys`+JSON-парсинг
  строки лога, не только «не упало»; изоляция между двумя пользователями;
  полный цикл `/model` → клавиатура с пометкой «(недоступна)» на боевой
  `anthropic/claude-3-haiku` → выбор доступной модели через реальный
  `CallbackQueryHandler` → подтверждение с обновлённой клавиатурой;
  попытка выбрать `UNAVAILABLE`-модель через callback отклонена, видна
  пользователю (`show_alert=True`), список не редактируется. Точечно
  исправлен докстринг `application/prompt/services/prompt_builder.py`
  (строка про `preferred_model`: «Этап 10» → «Этап 9» — единственное
  разрешённое отклонение от «не трогать Prompt Engine», backlog_7.md §3;
  `git diff` подтверждает ровно одну изменённую строку, без изменения
  логики). Собран реальный Docker-образ (`docker compose build`) —
  подтверждено прямым импортом внутри образа, что `catalog.json`
  установлен пакетом (`pip install .`, `pyproject.toml::package-data`) и
  `ConfigModelCatalogRepository()` реально читает 6 моделей из
  `/usr/local/lib/python3.11/site-packages/dekoder/infrastructure/
  model_catalog/catalog.json`; `alembic upgrade head → downgrade -1 →
  upgrade head` внутри контейнера проходит дважды — на чистой временной
  БД и на РЕАЛЬНОМ персистентном volume, оставшемся от предыдущих
  сессий тестирования Sprint 1-6 (ревизия `82d9884e32a2` до, `ed5701d2f683`
  после, таблица `user_active_models` подтверждена прямым запросом к
  `sqlite_master`); полный `docker compose up -d` (api + telegram-bot +
  qdrant) — `/health` отвечает `200`, оба сервиса стартуют и логируют
  штатно (`database_engine_initialized`, `database_connection_verified`,
  `qdrant_collection_already_exists`), ни одной ошибки/traceback в логах
  ни одного сервиса. Полный набор тестов (741), Ruff, Ruff format, MyPy
  проходят. `README.md` обновлён (см. ниже). Новая бизнес-функциональность
  не добавлена — Sprint 7 (S7-01…S7-08) полностью завершён — см. §36 для
  подробностей.

## Текущий спринт (обновление 6)

**Спринт 8: административные функции — защищённый REST API для CRUD
документов базы знаний и профилей, реальные health-check Qdrant/
OpenRouter/OpenAI, CLI-паритет — завершён (S8-01…S8-11).**

Цель и полный состав спринта — внешняя архитектурная спецификация
`backlog_8.md` (12 ADR, не входит в этот репозиторий) и §33 ниже.
Реализует Этап 10 «Плана реализации.md». Прогресс по задачам:

* [x] S8-01 — удаление мёртвого v2.0-скелета `application/admin/`
  (`AdminAuthPort`, `AuthenticateAdminCommand`, `AuthenticateAdminUseCase`
  — login/session-модель, несовместимая с выбранной статичной
  API-key-авторизацией). Отклонение от буквального текста задачи:
  `composition/container.py` (формально «не трогать») импортировал
  `AdminAuthPort`/`AuthenticateAdminUseCase` на уровне модуля — после
  удаления `application/admin/` этот импорт стал бы падать, транзитивно
  ломая `composition/bootstrap.py::create_app`, который использует
  тестируемый `tests/integration/test_health_endpoint.py`. Минимальная
  правка: удалены два dangling-импорта и два неиспользуемых поля
  (`admin_auth`, `authenticate_admin`) из мёртвого, никогда не
  создаваемого `Container`-датакласса — `build_container()` там
  по-прежнему `raise NotImplementedError`. `grep -RIn "application\.admin"
  src tests` — без совпадений.
* [x] S8-02 — `shared/config.py::AdminSettings` (`env_prefix="ADMIN_"`,
  `api_key: SecretStr` без default, `health_check_timeout: float = 3.0`),
  `presentation/api/dependencies/auth.py::require_admin_api_key`
  (`APIKeyHeader`, `secrets.compare_digest`, единообразный 401 на
  отсутствие/неверный ключ), `_SENSITIVE_KEYS` += `admin_api_key`/
  `x-admin-api-key`/`provided_key`. `.env`/`.env.example` дополнены
  `ADMIN_API_KEY`/`ADMIN_HEALTH_CHECK_TIMEOUT` (`.env` не отслеживается
  git). Три существующих теста, создающих полный `Settings()`, дополнены
  `ADMIN_API_KEY` в окружении.
* [x] S8-03 — `bootstrap/application.py::_lifespan` публикует
  `settings`/`openai_http_client`/`qdrant_client` на `app.state`, четыре
  новые accessor-функции (`get_settings`/`get_db_session_factory`/
  `get_openai_http_client`/`get_qdrant_client`); `shared/errors.py::
  NotFoundError` (сиблинг `ValidationError`/`ApplicationError`/
  `InfrastructureError`); `presentation/api/error_handlers.py` —
  `dekoder_error_handler` (422/404/502/400 по типу + code-override 409
  для `PROFILE_ARCHIVE_DEFAULT_FORBIDDEN`) и `unhandled_exception_handler`
  (500, нейтральное тело, полный traceback только в логах), оба
  зарегистрированы глобально в `create_application()`. `GET /health`
  (`composition/health.py`) не изменён ни строкой.
* [x] S8-04 — `KnowledgeDocumentRepository.list_all()` (порт + SQLAlchemy,
  `ORDER BY created_at DESC, id DESC`, без пагинации), `ListKnowledgeDocumentsUseCase`/
  `GetKnowledgeDocumentUseCase` (тонкие read-обёртки), `ReindexKnowledgeDocumentUseCase`
  (читает байты через `DocumentStorage.read()`, делегирует весь конвейер
  уже существующему `IndexKnowledgeDocumentUseCase` — переиспользование
  checksum-дедупликации ADR-6.9 сохраняет `document_id`); три новых
  билдера в `bootstrap/knowledge_container.py`. `IndexKnowledgeDocumentUseCase`/
  `DeleteKnowledgeDocumentUseCase` не изменены по существу.
* [x] S8-05 — `presentation/api/dependencies/documents.py` (`get_admin_session`
  — per-request `session_scope()`, `DocumentUseCases`, `get_document_use_cases`),
  `presentation/api/schemas/documents.py::DocumentResponse` (без
  `checksum`), `presentation/api/routes/admin_documents.py::
  admin_documents_router` (`POST`/`GET`/`GET{id}`/`DELETE{id}`/
  `POST{id}/reindex`, `require_admin_api_key` на уровне `APIRouter`,
  `DELETE` идемпотентен). Добавлена рантайм-зависимость
  `python-multipart` (иначе `Form`/`UploadFile` падают 500 на рантайме).
  Отклонение: импорт `admin_documents_router` в `create_application()`
  сделан локальным (внутри функции) — иначе цикл `bootstrap.application`
  → `presentation.api.routes.admin_documents` →
  `presentation.api.dependencies.documents` → `bootstrap.application`
  (зависимости документов импортируют accessor-функции из
  `bootstrap.application`); тот же приём применён к
  `admin_profiles_router`/`admin_health_router` в S8-08/S8-09. Новый
  `tests/support/fake_qdrant_client.py` — duck-typed фейк, принимающий
  реальные объекты `qdrant_client.models`, для тестов без реального
  Qdrant-сервера.
* [x] S8-06 — `ProfileRepository.get_by_id`/`create`/`update`/`archive`/
  `list_all` (порт + `SQLAlchemyProfileRepository`, тот же стиль, что
  `SQLAlchemyKnowledgeDocumentRepository` — НЕ копирует `select_profile()`'s
  собственный `session.commit()`). Никакой новой Alembic-миграции —
  подтверждено эмпирически (`alembic upgrade head → downgrade -1 →
  upgrade head`, 6 файлов в `alembic/versions/` до и после).
* [x] S8-07 — `CreateProfile`/`UpdateProfile`/`DeactivateProfile`/
  `ListAllProfiles` (`application/profile/use_cases/*`) поверх той же
  `ConversationRepositoriesFactory`; `CreateProfile` всегда
  `is_system=False, is_default=False`; `UpdateProfile` — `dataclasses.
  replace()` поверх `UpdateProfileCommand.changed_fields()` (партиальный
  PATCH, `is_default`/`is_system`/`status` физически отсутствуют в
  команде); `DeactivateProfile` — единственное место, проверяющее
  `is_default` перед архивированием, поднимает `ApplicationError(code=
  "PROFILE_ARCHIVE_DEFAULT_FORBIDDEN")`. `ApplicationContainer` получил
  ровно 4 новых профильных поля. Логирование по конвенции: `admin_profile_created`/
  `_updated`/`_archived`, без полного текста профиля.
* [x] S8-08 — `presentation/api/schemas/profiles.py`/`routes/admin_profiles.py::
  admin_profiles_router` (`GET`/`POST`/`GET{id}`/`PATCH{id}`/
  `POST{id}/archive`). Request-схемы физически не содержат
  `is_default`/`is_system`/`status`. Отклонение: `GET /admin/profiles/{id}`
  не получил отдельного use case'а «GetProfile» — ADR-8.4 фиксирует
  ровно 4 новых профильных поля контейнера без пятого; роут переиспользует
  `list_all_profiles` и фильтрует по id на уровне presentation.
  `presentation/telegram/handlers/profile.py` не изменён ни строкой
  (`git diff` пуст).
* [x] S8-09 — `application/health/ports.py` (`ServiceStatus`,
  `ServiceHealthCheck` Protocol — новый узкий bounded-context, не
  `application/admin/`), `application/health/use_cases/
  check_external_services.py::CheckExternalServicesHealthUseCase`,
  три адаптера в `infrastructure/health/` (Qdrant/OpenRouter/OpenAI),
  каждый переиспользует уже открытые клиенты (никаких новых). Уточнение
  сверх буквального текста ADR-8.9: `CheckExternalServicesHealthUseCase`
  дополнительно оборачивает каждый `check()` собственным `try/except`
  (`_run_one`, defense in depth) — задача явно требовала подтвердить, что
  `execute()` не падает даже если один фейк нарушает контракт и
  поднимает исключение вместо `ServiceStatus(healthy=False)`. `GET
  /admin/health` (`admin_health_router`) — всегда 200, даже если все три
  сервиса недоступны (`all_healthy=false`, не 5xx). `GET /health` не
  тронут.
* [x] S8-10 — `scripts/index_document.py` дополнен подкомандами
  `list`/`reindex`, переиспользующими билдеры `bootstrap/
  knowledge_container.py` (не дублируют логику); скрипт не переименован.
  Новый `scripts/check_services.py` — тонкая CLI-обёртка над
  `CheckExternalServicesHealthUseCase`, без admin-ключа (CLI и так
  требует доступа к `.env`/файловой системе сервера), exit code 0/1 по
  `all_healthy`.
* [x] S8-11 — финальная интеграция. Полный аудит `bootstrap/
  application.py`/`bootstrap/container.py`/`bootstrap/knowledge_container.py`
  не выявил дефектов сверх уже найденных и исправленных по ходу задач
  S8-01/S8-05 (см. записи выше) — DI-сборка корректна, ровно одна
  `ConversationRepositoriesFactory` во всём приложении (`grep`
  подтверждает единственный вызов `build_conversation_repositories_factory`
  в `bootstrap/container.py`). Новый `tests/e2e/test_admin_scenario.py` —
  один continuous-прогон через реальный `create_application()` lifespan:
  auth 401 на всех трёх роутерах (документы/профили/health, отсутствие И
  неверный ключ), полный цикл документа (upload→list→get→reindex→
  delete→404), полный цикл профиля (create→patch→archive, включая 409 на
  попытке архивировать `is_default=True`), health-check (здоровый И
  нездоровый сценарий) — всё в одном тесте, одном `app`/lifespan, не
  изолированными кусочками (уже покрыто отдельными
  `test_admin_documents.py`/`test_admin_profiles.py`/`test_admin_health.py`
  из S8-05/S8-08/S8-09). `git diff --stat feature/sprint-7..HEAD --
  domain/prompt application/prompt infrastructure/prompts
  process_user_message.py presentation/telegram` — пусто. Реальная
  Docker-верификация (не сфабрикована, Docker Desktop запущен и
  проверен): `docker compose build && docker compose up -d` — все три
  сервиса (api/telegram-bot/qdrant) стартуют штатно, `api` сообщает
  `healthy` через встроенный healthcheck; `GET /health` → `200`; `GET
  /admin/health` с реальным `ADMIN_API_KEY` из `.env` и РЕАЛЬНЫМИ
  `OPENROUTER_API_KEY`/`OPENAI_API_KEY` → `200`, все три сервиса
  `healthy: true` (Qdrant виден по имени сервиса `qdrant` из
  docker-compose сети — не заглушка); `GET /admin/health` без ключа/с
  неверным ключом → `401` оба раза; `alembic current`/`history` внутри
  контейнера подтверждают ровно 6 миграций (без новых для
  `profiles`/`knowledge_documents`); `alembic upgrade head → downgrade -1
  → upgrade head` внутри контейнера — чисто, `sqlite_master` после цикла
  содержит все 8 таблиц (включая `profiles`/`knowledge_documents`/
  `user_active_models`); `scripts/check_services.py`/`scripts/
  index_document.py list` отработали внутри контейнера штатно; полный
  реальный документный цикл выполнен внутри контейнера сквозь ОБА
  интерфейса разом — `index` через CLI (реальный OpenAI embeddings-вызов,
  реальный Qdrant upsert, `chunk_count=1`) → документ виден через `GET
  /admin/documents` (REST) → `reindex` через REST (тот же `document_id`)
  → `delete` через CLI → `GET /admin/documents/{id}` (REST) → `404`;
  попытка архивировать РЕАЛЬНЫЙ сид-профиль `is_default=True` («Деловой»,
  из сид-миграции S3-04) через REST против реального контейнера → `409`.
  Полный набор тестов (842), Ruff, Ruff format, MyPy проходят.
  `README.md`/`claude.md` обновлены под фактическое состояние Sprint 8.
  Новая бизнес-функциональность в этой задаче не добавлялась — только
  верификация и документация.

---

# 33. План следующих спринтов

## Спринт 2

* User;
* Conversation;
* Message;
* SQLite;
* SQLAlchemy;
* Alembic;
* repositories;
* история сообщений;
* политика контекста;
* `/new`;
* `/clear`.

## Спринт 3

* пользовательские профили;
* профиль по умолчанию;
* выбор профиля;
* применение профиля к ответам.

## Спринт 4

* Prompt Engine;
* шаблоны;
* версии;
* token budget;
* сборка контекста.

## Спринт 5

* долговременная память;
* явное сохранение;
* просмотр;
* удаление;
* релевантный поиск памяти.

## Спринт 6

* загрузка документов;
* parsing;
* chunking;
* embeddings;
* Qdrant;
* RAG;
* источники.

## Спринт 7

* каталог моделей;
* выбор модели;
* несколько AI-провайдеров;
* fallback policy.

## Спринт 8 — завершён (S8-01…S8-11, см. §32 «Текущий спринт (обновление 6)»)

* [x] административные функции — защищённый REST API (`presentation/api/`)
  для CRUD документов базы знаний (список/детали/загрузка+индексация/
  удаление/переиндексация) и профилей (список/создание/редактирование/
  архивация), статичная API-key авторизация (`X-Admin-Api-Key`/
  `ADMIN_API_KEY`), CLI-паритет (`scripts/index_document.py list/reindex`,
  `scripts/check_services.py`);
* [x] реальные health-check внешних сервисов (`GET /admin/health` —
  Qdrant/OpenRouter/OpenAI), `GET /health` остался дешёвым/без auth;
* [x] аудит-логирование административных действий (`admin_profile_created`/
  `_updated`/`_archived`, `knowledge_document_reindex_requested` — через
  уже существующий `structlog`-механизм, не отдельная подсистема);
* [x] явный глобальный `exception_handler` для FastAPI
  (`bootstrap/application.py`/`presentation/api/error_handlers.py`) —
  до Sprint 8 непокрытая граница интерфейса опиралась на дефолтное
  поведение Starlette (`debug=False` → общий `500` без traceback), т.к.
  единственный эндпоинт был `/health` и не мог бросить содержательное
  исключение; с первым эндпоинтом, вызывающим use case/бизнес-логику,
  понадобилась та же явная обработка `DekoderError`/неожиданных
  исключений, что уже есть в Telegram-обработчике (`presentation/
  telegram/handlers/messages.py`) — безопасное сообщение пользователю,
  без stack trace и внутренних деталей.
* [ ] полноценный просмотр/агрегация логов и метрик, полная иерархия
  ошибок §17.4 «Плана реализации.md» — явно отложены пользователем на
  этапе планирования Sprint 8 (скоуп-решение №3, backlog_8.md §1) на
  Этап 11, не входили в объём этого спринта;
* [ ] CRUD каталога AI-моделей, admin-управление долговременной памятью
  (`MemoryRecord` cross-user) — явно отклонены пользователем на этапе
  планирования (backlog_8.md §1, скоуп-решения №2/№3), не Sprint 8.

Порядок может корректироваться, но изменение должно быть зафиксировано.

---

# 34. Критические инварианты проекта

Следующие правила нельзя нарушать даже при сжатии контекста:

1. Проект — модульный монолит, не микросервисы.
2. Бизнес-логика не зависит от Telegram и FastAPI.
3. Бизнес-логика не зависит от OpenRouter.
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

> «Декодер» — персональный AI-ассистент на Python 3.11. Архитектура: Modular Monolith + Clean Architecture + Ports and Adapters. Основной интерфейс MVP — Telegram. Application не зависит от Telegram, FastAPI, OpenRouter, SQLAlchemy или Qdrant. AI вызывается через порт `LLMProvider`; первая реализация — `OpenRouterLLMAdapter`. Все зависимости собираются в bootstrap. Разработка идёт вертикальными срезами. Текущий первый срез: Telegram → `ProcessUserMessage` → `LLMProvider` → OpenRouter → ответ. Не добавлять память, RAG, профили, SQLAlchemy и Qdrant до соответствующего спринта. Перед завершением изменений запускать Ruff, MyPy и pytest.

---

# 36. Журнал текущего состояния

Этот раздел необходимо обновлять после завершения заметных задач.
Переписан по итогам завершения Спринта 1 целиком (Telegram-слой,
Docker, e2e-тест, README) и актуализации README/§32. Дополнен по итогам
задач S2-01 (подключение SQLAlchemy/Alembic), S2-02 (доменная модель
`User`/`Conversation`/`Message`, ORM, mapper, первая миграция), S2-03
(`UserRepository`), S2-04 (`ConversationRepository`), S2-05
(`MessageRepository`), S2-06 (расширение `ProcessUserMessage` историей
диалога — впервые подключены все три репозитория), S2-07
(`StartNewConversation` use case), S2-08 (подключение команды `/new` к
Telegram Adapter), S2-09 (`ClearConversation` use case), S2-10
(подключение команды `/clear` к Telegram Adapter) и S2-11 (финальная
интеграция и E2E-проверка) — Спринт 2 полностью завершён. Спринт 3
(пользовательские профили, S3-01…S3-09), Спринт 4 (Prompt Engine,
S4-01…S4-08) и Спринт 5 (долговременная память, S5-01…S5-08)
документированы подробно в §32 («Текущий этап разработки») — их
отдельные записи не дублируются построчно в этот раздел тем же
хронологическим стилем, что и Спринт 2; актуальное итоговое состояние
после Sprint 5 — в подразделах «В разработке»/«Не реализовано»/
«Известные расхождения»/«Следующее действие» ниже.

## Реализовано

Вертикальный срез работает целиком, включая вход через Telegram:

* `src/dekoder/shared/config.py` — `Settings` (`ApplicationSettings`,
  `TelegramSettings`, `LLMSettings`, `OpenRouterSettings`), pydantic-settings,
  секреты через `SecretStr`, без значений по умолчанию;
* `src/dekoder/shared/logging.py` — structlog, JSON в stdout,
  `timestamp`/`level`/`event`/`logger`/`environment` обязательны,
  `correlation_id`/`provider`/`model`/`duration` — по месту через
  `bind_request_context()`; редактирование чувствительных полей;
* `src/dekoder/shared/errors.py` — иерархия ошибок (см. §20, только 5 классов);
* `src/dekoder/domain/conversation/value_objects.py` — `MessageText`,
  `ModelId`, `ProviderId` (frozen+slots dataclass, без внешних зависимостей);
* `src/dekoder/application/conversation/dto.py` — `ProcessUserMessageCommand`,
  `ProcessUserMessageResult`, `LLMRequest`, `LLMResponse`, `TokenUsage`;
* `src/dekoder/application/conversation/ports.py` — `LLMProvider(Protocol)`,
  async, `@runtime_checkable`;
* `src/dekoder/application/conversation/use_cases/process_user_message.py` —
  `ProcessUserMessage`, зависит только от `LLMProvider` + DTO + `MessageText`;
* `src/dekoder/infrastructure/llm/{schemas.py,openrouter_adapter.py}` —
  `OpenRouterLLMAdapter(LLMProvider)`, httpx.AsyncClient через конструктор,
  все ошибки → `LLMProviderError` с конкретным кодом;
* `src/dekoder/bootstrap/{container.py,application.py}` —
  `ApplicationContainer` (без DI-библиотеки), `create_application()`,
  жизненный цикл `httpx.AsyncClient` через FastAPI lifespan;
* `src/dekoder/main.py` — вызывает `bootstrap.application.create_application`;
* `src/dekoder/presentation/telegram/` — `/start`
  (`handlers/start.py`), обработчик текстовых сообщений
  (`handlers/messages.py`, единственное место presentation-слоя,
  вызывающее `ProcessUserMessage`), `mapper.py` (Update →
  `ProcessUserMessageCommand`, разбиение длинных ответов на части по
  лимиту Telegram), `bot.py` (сборка `telegram.ext.Application`);
* `src/dekoder/telegram_main.py` — второй процесс (long polling),
  тонкая обёртка над bootstrap, как `main.py`; `PYTHONUNBUFFERED=1` в
  образе обязателен — иначе structlog-логи этого процесса не долетают
  до `docker compose logs` (не TTY, буферизация stdout);
* `Dockerfile` + `docker-compose.yml` — один образ (`python:3.11-slim`,
  непривилегированный пользователь `dekoder`), два сервиса (`api` —
  uvicorn + healthcheck на `/health`, `telegram-bot` — polling),
  секреты только через `env_file: .env`, в образ не копируются;
  `Application.run_polling()` сам обрабатывает SIGINT/SIGTERM;
* `README.md` — переписан под реально работающий срез (было: описание
  `docs/versions/*_v2.0.md`, аспирационное); содержит инструкцию по
  локальному запуску (uv, `.env.local`, два процесса) и Docker;
* тесты на каждый пункт выше (`tests/unit/...`, `tests/integration/...`,
  `tests/e2e/test_conversation_scenario.py` — сквозной сценарий диалога
  поверх всего среза) — 143 теста, ruff/mypy/pytest проходят на каждом
  коммите (pre-commit).

**Спринт 2, S2-01 — подключение SQLAlchemy и Alembic (только
инфраструктура, без ORM-моделей/репозиториев/таблиц):**

* `src/dekoder/shared/config.py` — добавлен `DatabaseSettings`
  (`env_prefix="DATABASE_"`), поле `url` со значением по умолчанию
  `sqlite+aiosqlite:///./data/app.db` (относительный путь, без
  зависимости от конкретной машины), подключён к `Settings.database`;
* `src/dekoder/infrastructure/persistence/base.py` — единая
  `Base(DeclarativeBase)` для всех будущих ORM-моделей;
* `src/dekoder/infrastructure/persistence/engine.py` —
  `create_database_engine()` (единый `AsyncEngine`, `aiosqlite`,
  `echo=False` по умолчанию, URL логируется без пароля), централизованное
  включение `PRAGMA foreign_keys=ON` для каждого нового SQLite-соединения
  (`event.listens_for(engine.sync_engine, "connect")`),
  `verify_database_connection()` (`SELECT 1`, ошибка → `InfrastructureError`);
* `src/dekoder/infrastructure/persistence/session.py` —
  `create_session_factory()` (`async_sessionmaker`, `expire_on_commit=False`,
  `autoflush=False`) и `session_scope()` — единый механизм получения
  `AsyncSession` (commit при успехе / rollback при исключении / close всегда);
* `src/dekoder/bootstrap/database.py` — `init_database()` (каталог для
  SQLite-файла → engine → проверка подключения → session factory) и
  `dispose_database()`; единственное место, создающее каталог `./data/`
  (не файл БД и не таблицы — только Alembic создаёт схему);
* `src/dekoder/bootstrap/application.py` — `_lifespan` вызывает
  `init_database()` до приёма трафика (fail-fast при недоступной БД) и
  `dispose_database()` при остановке, в одном event loop'е (uvicorn);
  `AsyncEngine`/`async_sessionmaker` доступны через `app.state.db_engine`/
  `app.state.db_session_factory`;
* `src/dekoder/telegram_main.py` — DB-инициализация выполняется внутри
  `post_init` (а не до `run_polling()`) и disposal — внутри
  `post_shutdown`: `run_polling()` создаёт собственный event loop, а
  `aiosqlite`-соединения привязаны к тому loop'у, в котором были открыты;
  ошибка подключения к БД внутри `post_init` останавливает запуск процесса;
* `alembic/` + `alembic.ini` — инициализированы шаблоном `-t async`;
  `alembic/env.py` использует `DatabaseSettings().url` (не весь `Settings`
  — миграции не должны требовать `TELEGRAM_BOT_TOKEN`/`OPENROUTER_API_KEY`)
  и `target_metadata = Base.metadata` для autogenerate; `alembic.ini` без
  абсолютных путей (`%(here)s`), плейсхолдер `sqlalchemy.url` не
  используется (перезаписывается в `env.py`);
  `alembic/versions/` пока пуст (`.gitkeep`) — ORM-моделей ещё нет,
  `alembic upgrade head`/`downgrade base`/`upgrade head`/`revision
  --autogenerate` вручную проверены на пустом списке миграций;
* `.env.example` — добавлен `DATABASE_URL`; `.gitignore` — `data/*.db`,
  `data/*.sqlite`, `data/*.sqlite3` игнорируются, `data/.gitkeep`
  (пустой каталог) отслеживается через явное исключение;
  `pyproject.toml`/`uv.lock` — добавлены `sqlalchemy[asyncio]`,
  `aiosqlite`, `alembic` (`uv add`);
* тесты: `tests/unit/shared/test_config.py` (расширен —
  `DatabaseSettings`), `tests/integration/persistence/{test_engine.py,
  test_session.py}`, `tests/integration/test_database_bootstrap.py`,
  `tests/integration/test_application_bootstrap.py` (расширен —
  `DATABASE_URL` в тестовой фикстуре указывает на `tmp_path`, иначе
  реальный lifespan писал бы `./data/app.db` при прогоне тестов);
  Domain и Application Layer по-прежнему не импортируют SQLAlchemy
  (`domain/conversation`, `application/conversation` — проверено grep'ом).
* README.md — раздел «База данных и миграции» (команды `alembic
  upgrade/downgrade/current/history/revision --autogenerate`).

**Спринт 2, S2-02 — доменные сущности `User`/`Conversation`/`Message`,
ORM-модели, mapper Domain↔ORM, первая Alembic-миграция схемы (без
репозиториев и без изменений `ProcessUserMessage`/`/new`/`/clear` —
следующая задача Sprint 2):**

* `src/dekoder/domain/user/entities.py` — `User` (frozen dataclass,
  `slots=True`): `id: UUID`, `telegram_user_id: int`, `created_at`/
  `updated_at: datetime`. Инварианты в `__post_init__` (обычный
  `ValueError`, как в `value_objects.py` — claude.md §20):
  `telegram_user_id > 0`, `updated_at >= created_at`; неизменность
  `telegram_user_id` после создания обеспечивается `frozen=True` — в
  Sprint 2 нет сценария, обновляющего `User`. Новый подпакет
  `domain/user/` (не внутри `domain/conversation/`) — `User` не входит в
  агрегат `Conversation`;
* `src/dekoder/domain/conversation/entities.py` — рядом с уже
  существующим `value_objects.py`: `MessageRole` (`Enum`: `USER`,
  `ASSISTANT` — только эти два значения, без system/tool/function),
  `Message` (frozen dataclass, неизменяем — нет `updated_at` и методов
  изменения; инвариант — `content.strip()` не пустой) и `Conversation`
  (Aggregate Root, ADR-2.3: `dataclass(slots=True)`, НЕ frozen — метод
  `close(closed_at)` устанавливает `closed_at`/обновляет `updated_at`,
  запрещает повторное закрытие и `closed_at` раньше `created_at`;
  свойство `is_active`). Ни один из трёх файлов не импортирует
  SQLAlchemy — проверено grep'ом (см. ниже);
* `src/dekoder/infrastructure/persistence/{user_orm.py,
  conversation_orm.py,message_orm.py}` — typed declarative ORM-модели
  (`Mapped[...]`/`mapped_column(...)`) поверх `Base` (S2-01), по одному
  файлу на сущность. Без `relationship()` — доступ к диалогам/сообщениям
  через будущие репозитории (S2-03+), не через ORM-навигацию; это же
  исключает случайную загрузку всей истории сообщений (`lazy="joined"`)
  и ORM-каскады, которые заменили бы будущую явную реализацию `/clear`.
  Явные стабильные имена ограничений/индексов: `uq_users_telegram_user_id`,
  `ix_conversations_user_id`, `uq_conversations_active_user` (частичный
  уникальный индекс — `sa.Index(..., unique=True, sqlite_where=sa.text(
  "closed_at IS NULL"))` — единственная защита инварианта «не более
  одного активного диалога на пользователя» на уровне БД: обычный
  `UNIQUE(user_id, closed_at)` недостаточен, SQL допускает несколько
  строк с `NULL`), `ck_messages_role`, `ck_messages_content_not_empty`
  (`length(trim(content, ' ' || char(9) || char(10) || char(13))) > 0` —
  **не** просто `trim(content)`: SQLite `trim(X)` без второго аргумента
  обрезает только пробелы (0x20), не табы/переводы строк — строка из
  одних табов проходила бы как «непустая», обнаружено интеграционным
  тестом при реализации задачи), `ix_messages_conversation_created`
  (составной, `(conversation_id, created_at)`). `role` — обычный
  `String` + `CheckConstraint`, не `sqlalchemy.Enum` — доменный
  `MessageRole` остаётся чистым Python Enum;
* `src/dekoder/infrastructure/persistence/mappers.py` — явные функции
  `user_to_orm/user_to_domain`, `conversation_to_orm/
  conversation_to_domain`, `message_to_orm/message_to_domain`. Не делают
  запросов, не коммитят. Отдельно решена проблема таймстемпов: домен
  всегда использует timezone-aware UTC `datetime`, но SQLite не
  сохраняет offset (`DateTime(timezone=True)` возвращает *naive*
  `datetime` после round-trip через `aiosqlite` — проверено вручную)
  — mapper явно снимает tzinfo перед записью (`_to_naive_utc`) и
  восстанавливает `tzinfo=UTC` при чтении (`_to_aware_utc`);
* `src/dekoder/infrastructure/persistence/models.py` — единая точка
  импорта всех ORM-моделей ради побочного эффекта регистрации в
  `Base.metadata`; импортируется только из `alembic/env.py` (`# noqa:
  F401` — единственный оправданный, документированный случай) — иначе
  autogenerate не увидел бы таблицы;
* `alembic/versions/a96ab72bfa8a_create_users_conversations_messages.py`
  — первая миграция схемы: сгенерирована `alembic revision
  --autogenerate` и вручную выверена (autogenerate верно распознал CHECK
  и частичный индекс, но потребовалась ручная правка выражения `trim()`,
  см. выше, и порядка операций). `upgrade` создаёт таблицы `users` →
  `conversations` → `messages`, затем индексы; `downgrade` — строго в
  обратном порядке (сначала индексы, включая частичный, затем таблицы
  `messages` → `conversations` → `users`). `alembic check` подтверждает
  отсутствие расхождений между ORM-моделями и применённой миграцией.
  `alembic/env.py` дополнен импортом `infrastructure/persistence/models`
  (только ради регистрации метаданных, см. выше);
* тесты: `tests/unit/domain/{test_user_entity.py,
  test_conversation_entity.py,test_message_entity.py}` (инварианты,
  неизменяемость, `close()`); `tests/unit/infrastructure/persistence/
  test_mappers.py` (round-trip Domain→ORM→Domain для всех трёх сущностей,
  включая сохранение UTC-момента времени при разных исходных часовых
  поясах); `tests/integration/persistence/test_orm_constraints.py` на
  временной SQLite (`tmp_path`, схема — `Base.metadata.create_all()`,
  единственное допустимое исключение для тестового окружения,
  backlog_2.md §3): уникальность `telegram_user_id`, FK на
  несуществующего user/conversation, CHECK на роль и на пустой/
  пробельный `content`, и ключевой тест — второй активный диалог для
  одного пользователя падает `IntegrityError` на уровне БД (подтверждено
  вручную: `UNIQUE constraint failed: conversations.user_id`), после
  закрытия первого — создание нового активного проходит;
  `tests/integration/persistence/test_migrations.py` (`upgrade head` →
  `downgrade base` → `upgrade head`, синхронные тесты — `alembic/env.py`
  вызывает `asyncio.run()`, что упало бы `RuntimeError` из уже
  работающего event loop `async def`-теста под `pytest-asyncio`);
  Domain Layer по-прежнему не импортирует SQLAlchemy (`domain/
  conversation`, `domain/user` — проверено grep'ом), `create_all()` не
  вызывается нигде в рабочем коде (`grep -rn "create_all(" src` — пусто,
  единственная ссылка на `Base.metadata.create_all` — в тестовой
  фикстуре).

**Спринт 2, S2-03 — `UserRepository`: порт + SQLAlchemy-реализация +
bootstrap-фабрика (без `ConversationRepository`/`MessageRepository`, без
изменений `ProcessUserMessage`/`/new`/`/clear` — следующая задача Sprint 2):**

* `src/dekoder/application/user/ports.py` — `UserRepository(Protocol)`,
  `@runtime_checkable`, тот же стиль, что и `LLMProvider`
  (`application/conversation/ports.py`). Отдельный подпакет
  `application/user/` (не `application/conversation/`) — по аналогии с
  тем, куда S2-02 положил доменную сущность (`domain/user/`, не
  `domain/conversation/`): `User` не входит в агрегат `Conversation`.
  Методы: `get_by_id`, `get_by_telegram_user_id` (оба — `User | None`,
  отсутствие записи не исключение), `save` (сохраняет НОВУЮ сущность;
  отдельного `update()` нет — `User` в Sprint 2 без изменяемых полей
  бизнес-смысла), `get_or_create_by_telegram_user_id` (идемпотентна).
  Сигнатуры используют только доменные типы и типы стандартной
  библиотеки — ни одного упоминания SQLAlchemy (проверено grep'ом,
  см. ниже);
* `src/dekoder/infrastructure/persistence/user_repository.py` —
  `SQLAlchemyUserRepository`, реализует порт структурно (без
  наследования), поверх `UserORM`/`mappers.py` (S2-02). `AsyncSession`
  получает через конструктор, не создаёт и не закрывает её сама, не
  раскрывает `UserORM` наружу (все публичные методы возвращают `User`).
  Транзакционная политика: `get_by_id`/`get_by_telegram_user_id` — только
  `SELECT`; `save()` делает `add()` + `flush()` БЕЗ `commit()` (момент
  фиксации остаётся за вызывающим кодом/`session_scope()`), при
  `IntegrityError` — `rollback()` и `InfrastructureError`;
  `get_or_create_by_telegram_user_id()` — единственное исключение с
  собственным `commit()`/`rollback()` внутри (автономная операция без
  сетевых вызовов, backlog_2.md §8 это прямо допускает). Разрешение
  гонки: сначала `SELECT` по `telegram_user_id` → если не найден, `INSERT`
  + `commit()` → при `IntegrityError` — `rollback()`, проверка, что это
  именно нарушение `uq_users_telegram_user_id` (подстрока
  `"users.telegram_user_id"` в `exc.orig` — SQLite не передаёт имя
  constraint'а), а не произвольная ошибка целостности → повторный `SELECT`
  по `telegram_user_id` → найден — вернуть найденного; не найден или
  `IntegrityError` был не про `telegram_user_id` — `InfrastructureError`
  (исходная ошибка не глотается молча). Единственный источник истины
  против дублей — уникальное ограничение БД (S2-02), не `SELECT`-затем-
  `INSERT` на уровне Python;
* `src/dekoder/bootstrap/repositories.py` — `build_user_repository(session)
  -> UserRepository`, единственное место, знающее одновременно про порт и
  `SQLAlchemyUserRepository` (правило единственной точки сборки,
  claude.md §8.5). Сознательно НЕ подключено ни в `ApplicationContainer`,
  ни в `ProcessUserMessage` — расширение сценария историей диалога
  запланировано отдельной задачей Sprint 2 (S2-06);
* тесты: `tests/unit/application/test_user_repository_port.py` (контракт
  на fake in-memory реализации — `get_by_id`/`get_by_telegram_user_id`
  найден/не найден, `save`, идемпотентность `get_or_create`);
  `tests/integration/persistence/test_user_repository.py` (SQLAlchemy-
  реализация на временной SQLite — `get_by_id`/`get_by_telegram_user_id`,
  `save` + дубликат `telegram_user_id` → `InfrastructureError`,
  повторный `get_or_create` возвращает того же пользователя,
  **обязательный тест конкурентности**: `asyncio.gather()` двух вызовов
  `get_or_create_by_telegram_user_id()` с одним `telegram_user_id`,
  каждый на собственной независимой `AsyncSession`, сходятся на одном
  `id`, в БД — ровно одна строка; ORM-модель не протекает наружу —
  явная проверка `isinstance(result, User)`/`not isinstance(result,
  UserORM)`); `tests/integration/test_repositories_bootstrap.py`
  (`build_user_repository()` возвращает структурно совместимую и реально
  работающую реализацию поверх SQLite). `grep -rln "sqlalchemy" src/
  dekoder/domain src/dekoder/application/conversation/ports.py src/
  dekoder/application/user/ports.py` — пусто; `ProcessUserMessage` не
  изменён; `ConversationRepository`/`MessageRepository`/Unit of Work не
  введены.

**Спринт 2, S2-04 — `ConversationRepository`: порт + SQLAlchemy-
реализация + bootstrap-фабрика (без `MessageRepository`, без изменений
`ProcessUserMessage`/`/new`/`/clear` — следующая задача Sprint 2):**

* `src/dekoder/application/conversation/ports.py` — расширен: рядом с
  `LLMProvider` добавлен `ConversationRepository(Protocol)`,
  `@runtime_checkable`, тот же стиль. Порт живёт в
  `application/conversation/` (не в отдельном подпакете, как
  `UserRepository` в `application/user/`) — `Conversation` входит в
  conversation-агрегат (ADR-2.3), в отличие от `User`. Методы:
  `get_by_id`, `get_active_by_user_id` (оба — `Conversation | None`,
  активность строго `closed_at is None`, отсутствие — не исключение),
  `save` (сохраняет НОВЫЙ диалог, нарушение
  `uq_conversations_active_user` не скрывается), `close` (принимает
  сущность, уже закрытую доменным методом `Conversation.close(...)` —
  проверка инвариантов остаётся в Domain Layer), `get_or_create_active`
  (идемпотентна). Сигнатуры используют только доменные типы — ни одного
  упоминания SQLAlchemy (проверено grep'ом, см. ниже);
* `src/dekoder/infrastructure/persistence/conversation_repository.py` —
  `SQLAlchemyConversationRepository`, реализует порт структурно, поверх
  `ConversationORM`/`mappers.py` (S2-02), тот же стиль, что и
  `SQLAlchemyUserRepository`. Не проверяет существование пользователя и
  не вызывает `UserRepository` — эту гарантию даёт внешний ключ
  `conversations.user_id → users.id`; получение/создание `User` —
  ответственность вызывающего Use Case. `get_active_by_user_id()`
  использует `scalar_one_or_none()` (не `.first()`) — если БД вопреки
  `uq_conversations_active_user` содержит больше одного активного
  диалога, метод падает (`MultipleResultsFound`, обёрнут в
  `InfrastructureError`), а не молча выбирает первую строку. `close()`
  получает ORM-запись через `session.get()` и точечно обновляет только
  `closed_at`/`updated_at` — сознательно БЕЗ `session.merge()`, чтобы не
  перезаписать `user_id`/`created_at`; вызов `close()` с ещё активной
  сущностью (`closed_at is None`) — `ValidationError` (ошибка вызова
  контракта, не тихая перезапись); отсутствие записи с данным `id` в БД
  на момент `close()` — `InfrastructureError` (в отличие от `get_by_id`,
  где отсутствие нормально: вызывающий код уже должен был получить эту
  сущность через репозиторий раньше). Транзакционная политика — как у
  `UserRepository`: `save()`/`close()` делают `flush()` без `commit()`
  (момент фиксации — за вызывающим кодом), `get_or_create_active()` —
  самостоятельная транзакция с `commit()`/`rollback()` внутри. Разрешение
  гонки: `SELECT` активного → не найден → `INSERT` + `commit()` → при
  `IntegrityError` — `rollback()`, проверка подстроки
  `"conversations.user_id"` в `exc.orig` (единственная UNIQUE-ошибка на
  этой колонке — частичный индекс `uq_conversations_active_user`; FK-
  нарушение даёт другое сообщение — `"FOREIGN KEY constraint failed"`,
  проверено вручную) → повторный `SELECT` активного → найден — вернуть;
  не найден или `IntegrityError` был не про активный диалог —
  `InfrastructureError` (исходная ошибка не глотается молча);
* `src/dekoder/bootstrap/repositories.py` — добавлена
  `build_conversation_repository(session) -> ConversationRepository`,
  рядом с `build_user_repository`, тем же стилем. Сознательно НЕ
  подключена ни в `ApplicationContainer`, ни в `ProcessUserMessage` —
  как и `build_user_repository` (S2-03), расширение сценария историей
  диалога запланировано отдельной задачей Sprint 2 (S2-06);
* тесты: `tests/unit/application/test_conversation_repository_port.py`
  (контракт на fake in-memory реализации — активный диалог найден/не
  найден с игнорированием закрытых, `get_or_create_active` создаёт при
  первом вызове, идемпотентна при повторном, после `close()` создаёт
  новый диалог с другим `id`, старый остаётся в хранилище);
  `tests/integration/persistence/test_conversation_repository.py`
  (SQLAlchemy-реализация на временной SQLite — `save`+`get_by_id`
  round-trip, `get_active_by_user_id` находит активный/игнорирует
  закрытый, `close` обновляет только `closed_at`/`updated_at` и не трогает
  остальные поля, попытка сохранить диалог с несуществующим `user_id` →
  `InfrastructureError`/FK, запись не создана, **обязательный тест
  одного активного диалога** (второй активный того же пользователя →
  `InfrastructureError` → закрыть первый → новый активный проходит),
  **обязательный тест конкурентности** (`asyncio.gather()` двух
  `get_or_create_active()` на независимых `AsyncSession` для одного
  `user_id` — сходятся на одном `id`, в БД ровно одна активная строка),
  проверка отсутствия eager-load `messages` (`not hasattr(result,
  "messages")` — тривиально верно: у домена `Conversation` в принципе
  нет такого поля, а `ConversationORM` не имеет `relationship()`, см.
  S2-02); `tests/integration/test_repositories_bootstrap.py` расширен
  (`build_conversation_repository()` возвращает структурно совместимую и
  реально работающую реализацию). `grep -rln "sqlalchemy" src/dekoder/
  domain src/dekoder/application/conversation/ports.py src/dekoder/
  application/user/ports.py` — пусто; `ProcessUserMessage` не изменён;
  `MessageRepository`/Unit of Work не введены.

**Спринт 2, S2-05 — `MessageRepository`: порт + SQLAlchemy-реализация +
bootstrap-фабрика (репозитории Sprint 2 завершены; без изменений
`ProcessUserMessage`/`/new`/`/clear` — следующая задача Sprint 2, S2-06):**

* `src/dekoder/application/conversation/ports.py` — расширен: рядом с
  `LLMProvider`/`ConversationRepository` добавлен
  `MessageRepository(Protocol)`, `@runtime_checkable`, тот же стиль. Порт
  живёт в `application/conversation/` (не в отдельном подпакете) — по
  аналогии с `ConversationRepository`: `Message` входит в
  conversation-агрегат (ADR-2.3). Методы: `save` (сохраняет НОВОЕ
  сообщение — никакого `update`/`edit`, сообщения неизменяемы; повторный
  `id` должен быть отклонён БД через первичный ключ, не скрывается),
  `history` (возвращает `list[Message]` всех сообщений диалога, строго
  `created_at ASC, id ASC`, пустая история — `[]`, не исключение и не
  `None`), `clear` (удаляет все сообщения диалога одной операцией,
  возвращает число удалённых строк — `int`, идемпотентна). Возвращаемый
  тип коллекции — `list[...]`, а не `Sequence[...]`: это единственная
  используемая в проекте конвенция для коллекций в сигнатурах портов (не
  считая мёртвого дерева `composition/`). Сигнатуры используют только
  доменные типы и типы стандартной библиотеки — ни одного упоминания
  SQLAlchemy (проверено grep'ом, см. ниже);
* `src/dekoder/infrastructure/persistence/message_repository.py` —
  `SQLAlchemyMessageRepository`, реализует порт структурно, поверх
  `MessageORM`/`mappers.py` (S2-02), тот же стиль, что и
  `SQLAlchemyUserRepository`/`SQLAlchemyConversationRepository`. Не
  проверяет существование диалога и не вызывает `ConversationRepository`
  — эту гарантию даёт внешний ключ `messages.conversation_id →
  conversations.id` (S2-02); получение/создание `Conversation` —
  ответственность вызывающего Use Case. Не решает роль сообщения, не
  формирует LLM-контекст, не считает токены, не суммирует/не кэширует
  историю. `history()` — typed `select()` с `.order_by(MessageORM.
  created_at.asc(), MessageORM.id.asc())` — вторичная сортировка по `id`
  обязательна для детерминизма при совпадающих `created_at` (подтверждено
  интеграционным тестом с искусственно одинаковым `created_at` и разными
  `id`). `clear()` — одна `sqlalchemy.delete()` с `WHERE conversation_id
  = ...`, не построчная загрузка и не ORM-каскад (`MessageORM` и так без
  `relationship()`, S2-02); число удалённых строк берётся из
  `CursorResult.rowcount` (`AsyncSession.execute()` для DML-`delete()`
  типизирован как `Result[Any]`, но во время выполнения это
  `CursorResult` — `cast()` к `CursorResult` понадобился, чтобы mypy не
  ругался на отсутствие `rowcount` на общем `Result`). Транзакционная
  политика — как у `UserRepository`/`ConversationRepository`: `save()`
  делает `add()` + `flush()` без `commit()` (момент фиксации — за
  вызывающим кодом), `history()` — только `SELECT`, `clear()` — `DELETE`
  + `flush()` без `commit()`, той же причине, что и `save()`. Нарушение
  первичного ключа при `save()` (повтор `id`) или внешнего ключа
  (неизвестный `conversation_id`) — `rollback()` + `InfrastructureError`,
  не глотается молча;
* `src/dekoder/bootstrap/repositories.py` — добавлена
  `build_message_repository(session) -> MessageRepository`, рядом с
  `build_user_repository`/`build_conversation_repository`, тем же стилем.
  Сознательно НЕ подключена ни в `ApplicationContainer`, ни в
  `ProcessUserMessage` — как и обе предыдущие фабрики, расширение
  сценария историей диалога (впервые подключающее все три репозитория)
  запланировано отдельной задачей Sprint 2 (S2-06);
* тесты: `tests/unit/application/test_message_repository_port.py`
  (контракт на fake in-memory реализации — `save` сохраняет и возвращает
  сущность с исходными `id`/`content`, пустая история → `[]`, история
  только своего диалога при нескольких диалогах в хранилище —
  изоляция, сообщения, добавленные не по порядку, возвращаются
  отсортированными по `created_at` затем `id`, `clear` удаляет только
  сообщения своего диалога, повторный `clear` на пустой истории → `0` без
  ошибки); `tests/integration/persistence/test_message_repository.py`
  (SQLAlchemy-реализация на временной SQLite — сохранение user- и
  assistant-сообщения с проверкой всех полей через `history()`, пустая
  история для только что созданного диалога, изоляция между двумя
  диалогами двух разных пользователей — у одного пользователя не может
  быть двух активных диалогов одновременно, `uq_conversations_active_user`
  из S2-02, поэтому тест использует двух пользователей, а не два диалога
  одного, попытка сохранить сообщение с несуществующим `conversation_id` →
  `InfrastructureError`/FK, запись не создана, `clear` реально удаляет
  строки — проверено прямым `COUNT`, `Conversation` и его `closed_at`
  остаются нетронутыми, **обязательный тест стабильности сортировки** —
  два сообщения с искусственно одинаковым `created_at`, но разными `id`
  (`00000000-...`/`ffffffff-...`, специально не совпадающими с порядком
  вставки), результат `history()` детерминирован по `id ASC`); `tests/
  integration/test_repositories_bootstrap.py` расширен
  (`build_message_repository()` возвращает структурно совместимую и
  реально работающую реализацию, связка `UserRepository` →
  `ConversationRepository` → `MessageRepository` поверх одной `AsyncSession`
  round-trip'ится). `grep -rln "sqlalchemy" src/dekoder/domain src/dekoder/
  application/conversation/ports.py src/dekoder/application/user/
  ports.py` — пусто (совпадения только в docstring'ах, упоминающих
  отсутствие зависимости от SQLAlchemy текстом); `ProcessUserMessage` не
  изменён; Unit of Work/Generic Repository не введены; `update`/`edit`/
  `change_role` для сообщений не существуют.

**Спринт 2, S2-06 — расширение `ProcessUserMessage` историей диалога
(впервые подключены все три репозитория Sprint 2 одновременно; `/new`/
`/clear` не реализованы — следующая задача Sprint 2):**

* `src/dekoder/application/conversation/dto.py` — `ProcessUserMessageCommand.
  external_user_id: str` переименован в `telegram_user_id: int` (единственный
  источник значения — `Update.effective_user.id`, Telegram SDK, всегда
  `int`; строковое промежуточное представление было артефактом Sprint 1,
  когда ещё не было ни одного репозитория); `ProcessUserMessageResult`
  расширен `conversation_id: UUID`/`message_id: UUID` (`message_id` —
  `id` сохранённого сообщения ассистента), `usage` остался последним
  полем со значением по умолчанию. `LLMRequest.user_message: MessageText`
  (одно сообщение) заменён на `LLMRequest.messages: Sequence[LLMMessage]`
  (вся история активного диалога); добавлен `LLMMessage(role: str,
  content: str)` — минимальная роль+текст без специфики конкретного SDK
  (OpenAI/OpenRouter/Anthropic/...), `role` — обычная `str`, не доменный
  `MessageRole` (`LLMRequest` — контракт LLM-порта, не диалоговый
  агрегат);
* `src/dekoder/application/conversation/ports.py` — добавлены
  `ConversationRepositories` (frozen dataclass — `users`/`conversations`/
  `messages`, по одному полю на каждый из трёх портов Sprint 2) и
  `ConversationRepositoriesFactory` (`Callable[[], AbstractAsyncContextManager[
  ConversationRepositories]]`). Это НЕ standalone Unit of Work
  (backlog_2.md §15, инвариант 14 — явно запрещён): `ConversationRepositories`
  не предоставляет `begin()`/`commit()`/`rollback()` и вообще не знает про
  транзакции — просто именованный набор уже существующих портов; момент
  открытия/коммита/отката транзакции остаётся инфраструктурной
  ответственностью `session_scope()` (S2-01), в которую фабрику оборачивает
  bootstrap. Это единственный способ, которым `ProcessUserMessage`
  получает доступ к хранилищу — сам use case не импортирует SQLAlchemy,
  `AsyncSession` или `async_sessionmaker` (проверено grep'ом, см. ниже);
* `src/dekoder/application/conversation/use_cases/process_user_message.py`
  — `ProcessUserMessage` теперь принимает `repositories:
  ConversationRepositoriesFactory` вторым параметром конструктора (после
  `llm_provider`). Поток `execute()`: провалидировать текст (без
  изменений, как в Sprint 1) → `_save_user_message()` (короткая
  транзакция 1: `UserRepository.get_or_create_by_telegram_user_id()` →
  `ConversationRepository.get_or_create_active()` → построить доменный
  `Message(id=uuid4(), role=USER, content=..., created_at=datetime.now(UTC))`
  → `MessageRepository.save()`; commit при выходе из `async with`) →
  `_load_history()` (короткая read-only транзакция 2, ВНЕ транзакции 1 и
  ВНЕ вызова LLM — отдельный вызов `self._repositories()`, как
  рекомендует backlog_2.md §9: «Вне транзакции: load history, call LLM») →
  построить `LLMRequest` (роль `MessageRole.USER/ASSISTANT` →
  `message.role.value`, история уже содержит только что сохранённое
  сообщение пользователя — оно НЕ добавляется повторно) → вызвать
  `LLMProvider.generate()` (полностью вне какой-либо открытой сессии) →
  `_save_assistant_message()` (короткая транзакция 3: построить доменный
  `Message(role=ASSISTANT, content=response.text, ...)` →
  `MessageRepository.save()`; commit при выходе из `async with`) →
  вернуть `ProcessUserMessageResult`. Три независимых коротких вызова
  `self._repositories()` вместо одной обёрнутой транзакции на весь
  сценарий — намеренно, чтобы: (а) пользовательское сообщение
  коммитилось до сетевого вызова LLM (обязательное требование задачи),
  (б) чтение истории не удерживало ту же транзакцию, что и запись, (в)
  ошибка сохранения ответа ассистента не откатывала уже закоммиченное
  сообщение пользователя. Обработка ошибок: `MessageRepository.save()`
  падает `InfrastructureError` → пробрасывается как есть, LLM не
  вызывается (ошибка при сохранении user message) или не вызывается
  повторно (ошибка при сохранении assistant message) — `ProcessUserMessage`
  не перехватывает и не оборачивает исключения репозиториев/LLM-провайдера
  дополнительно, использует существующую иерархию `shared/errors.py` как
  есть (как и в Sprint 1);
* `src/dekoder/infrastructure/llm/openrouter_adapter.py` —
  `OpenRouterLLMAdapter.generate()` строит `messages=[system, *history]`
  (распаковка `request.messages`, преобразованных 1:1 в
  `OpenRouterChatMessage(role=message.role, content=message.content)`)
  вместо `[system, user]` Sprint 1; `schemas.py` не менялся (`OpenRouterChatMessage`
  уже была `role`+`content`, wire-формат не изменился);
* `src/dekoder/bootstrap/repositories.py` — добавлена
  `build_conversation_repositories_factory(session_factory) ->
  ConversationRepositoriesFactory`: каждый вызов возвращённого callable
  открывает новую `session_scope()` и строит `ConversationRepositories` из
  уже существующих `build_user_repository`/`build_conversation_repository`/
  `build_message_repository` (S2-03/S2-04/S2-05) поверх этой сессии — эти
  три фабрики впервые подключены к реальному сценарию;
* `src/dekoder/bootstrap/container.py` — `build_container()` получил
  третий параметр `db_session_factory: async_sessionmaker[AsyncSession]`,
  собирает `repositories_factory` через `build_conversation_repositories_factory`
  и передаёт его в `ProcessUserMessage`;
* `src/dekoder/bootstrap/application.py` — `_lifespan` передаёт уже
  готовую `db_session_factory` (S2-01, `init_database()`) в
  `build_container()`; порядок вызовов не изменился (инициализация БД
  всё ещё предшествует сборке контейнера в одном и том же event loop
  uvicorn);
* `src/dekoder/presentation/telegram/bot.py` — `build_telegram_application()`
  разделена на `build_telegram_application(bot_token)` (только `/start`) и
  `register_message_handler(application, process_user_message)`
  (обработчик текста отдельно). Причина: `telegram_main.py` теперь должен
  собирать `ProcessUserMessage` (через `build_container()`, которому нужна
  `db_session_factory`) только ПОСЛЕ `init_database()`, а `init_database()`
  по-прежнему обязана выполняться внутри `post_init` `run_polling()`
  (S2-01: `aiosqlite`-соединения привязаны к event loop'у, в котором были
  открыты, `run_polling()` создаёт собственный loop) — до S2-06 весь
  `Application` собирался одной функцией до `run_polling()`, теперь
  обработчик текста регистрируется отдельно, внутри `post_init`;
* `src/dekoder/telegram_main.py` — `main()` больше не строит
  `ApplicationContainer`/`ProcessUserMessage` заранее: `build_telegram_application()`
  вызывается без `process_user_message` (только `/start`), а внутри
  `post_init` (`_startup`) — `init_database()` → `build_container()` →
  `register_message_handler()`, в этом порядке, в одном и том же event
  loop'е `run_polling()`;
* `src/dekoder/presentation/telegram/mapper.py` — `to_command()` передаёт
  `telegram_user_id=user.id` (`int` напрямую из `Update.effective_user.id`)
  вместо `external_user_id=str(user.id)`;
* `pyproject.toml` — добавлен `[tool.pytest.ini_options] pythonpath =
  ["."]`, чтобы тестовые модули могли импортировать общий helper
  `tests/support/fake_conversation_repositories.py` (in-memory
  fake-реализации `UserRepository`/`ConversationRepository`/
  `MessageRepository` + `ConversationRepositoriesFactory` поверх них, без
  SQLAlchemy) как пакет `tests.support...`;
* тесты: `tests/unit/application/test_process_user_message.py` переписан
  под новый контракт — richer in-memory fake-репозитории (с инструментацией
  `fail_on_save_call(n, error)` для инъекции сбоя сохранения N-го
  сообщения) + fake `LLMProvider`, без SQLAlchemy; покрывает все
  обязательные сценарии backlog_2_tasks.md (S2-06): новый пользователь
  (создание User+Conversation, сохранение user message, LLM получает
  историю, сохранение assistant message, возврат ответа), существующий
  пользователь/диалог (не создаются повторно, история продолжается),
  порядок и отсутствие дублирования истории, assistant message появляется
  в истории только после успешного LLM-вызова, следующий запрос видит
  предыдущий assistant message, ошибка LLM (user message сохранено,
  assistant отсутствует, ошибка проброшена), ошибка сохранения user
  message (LLM не вызывается), ошибка сохранения assistant message (user
  message остаётся, LLM не вызывается повторно), возвращаемый тип —
  `ProcessUserMessageResult`, не ORM/сырой SDK response; `tests/unit/
  application/test_llm_provider_port.py`, `tests/integration/llm/
  test_openrouter_adapter.py` (добавлен тест `[system, *history]` из трёх
  сообщений в правильном порядке), `tests/unit/presentation/telegram/
  {test_mapper.py,test_messages_handler.py}`, `tests/e2e/
  test_conversation_scenario.py` — адаптированы под новые сигнатуры
  (`telegram_user_id`, `request.messages`, `repositories=...`,
  `register_message_handler()`); `tests/integration/
  test_process_user_message_persistence.py` (новый, обязательный по
  backlog_2_tasks.md S2-06) — реальные SQLAlchemy-репозитории поверх
  временной SQLite (`tmp_path`, `Base.metadata.create_all()`) + fake LLM
  (без сети): первое сообщение → 2 записи `messages` (user, assistant),
  второе сообщение в том же диалоге → 4 записи, порядок ролей
  user/assistant/user/assistant, один `conversation_id`, второй вызов LLM
  реально получил `[{"Сообщение 1"}, {"Ответ 1"}, {"Сообщение 2"}]` —
  подтверждает, что история из БД действительно доходит до LLM-порта;
  `tests/integration/test_repositories_bootstrap.py` расширен —
  `build_conversation_repositories_factory()` (каждый вызов — независимая
  закоммиченная транзакция; исключение внутри `async with` откатывает
  незакоммиченную запись). `grep -rln "sqlalchemy" src/dekoder/application/
  conversation` — пусто (в т.ч. `process_user_message.py` не импортирует
  SQLAlchemy впрямую — единственная зависимость от хранилища,
  `ConversationRepositoriesFactory`, объявлена в `application/conversation/
  ports.py` через `Callable`/`AbstractAsyncContextManager`, оба —
  стандартная библиотека); Generic Repository/standalone Unit of
  Work/Domain Events/Prompt Engine/Memory/RAG/summary/token
  counting/retry/очереди — не добавлены; `/new`/`/clear` не реализованы.

**Спринт 2, S2-07 — `StartNewConversation` use case (Application Layer;
без изменений `ProcessUserMessage`, без подключения команды `/new` к
Telegram Adapter — следующая задача Sprint 2, S2-08):**

* `src/dekoder/application/conversation/dto.py` — добавлены
  `StartNewConversationCommand` (единственное поле — `telegram_user_id:
  int`, без `correlation_id`/`model_id`: use case не логирует и не
  вызывает LLM) и `StartNewConversationResult` (`conversation_id: UUID |
  None` — `None` означает «пользователь не найден», это штатный успешный
  исход, не ошибка), тот же стиль `dataclass(frozen=True)`, что и
  `ProcessUserMessageCommand`/`ProcessUserMessageResult`;
* `src/dekoder/application/conversation/use_cases/start_new_conversation.py`
  (новый файл) — класс `StartNewConversation`, конструктор принимает
  единственную зависимость `repositories: ConversationRepositoriesFactory`
  (тот же порт, что и второй параметр конструктора `ProcessUserMessage`,
  `application/conversation/ports.py`, задача S2-06) — переиспользование
  уже утверждённой фабрики короткой транзакции вместо введения нового,
  более узкого порта (backlog_2.md §15, инвариант 14 запрещает вводить
  новые абстракции хранения «на будущее»). `execute()`: получить `User`
  через `repositories.users.get_by_telegram_user_id()` (НЕ
  `get_or_create_...` — в отличие от `ProcessUserMessage`, пользователь не
  создаётся автоматически, backlog_2_tasks.md S2-07) → если `None` —
  вернуть `StartNewConversationResult(conversation_id=None)`, не создавая
  ни пользователя, ни диалог → получить активный диалог через
  `repositories.conversations.get_active_by_user_id()` → если найден —
  закрыть через доменный `Conversation.close(datetime.now(UTC))` (доменные
  инварианты — «нельзя закрыть уже закрытый», «нельзя закрыть раньше
  created_at» — проверяются в `domain/conversation/entities.py`, не
  здесь) и сохранить через `repositories.conversations.close(...)` →
  создать новый `Conversation(id=uuid4(), user_id=user.id, closed_at=None,
  ...)` и сохранить через `repositories.conversations.save(...)` →
  вернуть `StartNewConversationResult(conversation_id=...)`. Всё — внутри
  ОДНОГО вызова `self._repositories()` (одной короткой транзакции), в
  отличие от трёх раздельных транзакций `ProcessUserMessage`: там
  разделение было обязательным, чтобы не держать транзакцию БД открытой
  во время сетевого вызова `LLMProvider.generate()` (backlog_2.md §9);
  здесь сетевых вызовов нет вовсе, поэтому закрытие старого диалога и
  создание нового — единая атомарная операция (откатывается целиком при
  ошибке, не оставляет пользователя без активного диалога из-за сбоя
  между двумя шагами). `repositories.messages` (тот же объект, что и
  `MessageRepository`, доступный через `ConversationRepositories`) ни разу
  не вызывается ни в одном методе файла — задача прямо запрещает
  use case'у работать с историей сообщений («не работает с
  MessageRepository», «не удаляет сообщения предыдущего диалога»);
  `LLMProvider` не импортируется вовсе. `process_user_message.py` не
  изменён (подтверждено `git diff` — пустой);
* тесты: `tests/unit/application/test_start_new_conversation.py` (новый,
  in-memory fake-репозитории через общий helper `tests/support/
  fake_conversation_repositories.py`, S2-06, без SQLAlchemy) — пользователь
  отсутствует (успешный результат без `conversation_id`, пользователь не
  создан), активного диалога нет (новый диалог создаётся напрямую, без
  вызова `close`), активный диалог существует (закрывается через
  `Conversation.close()`, новый диалог получает другой `id`, становится
  единственным активным), повторный вызов создаёт очередной новый диалог
  (разные `id` на каждом вызове), старые диалоги не удаляются (остаются
  доступны через `get_by_id`); `tests/integration/
  test_start_new_conversation_persistence.py` (новый, реальные
  SQLAlchemy-репозитории поверх временной SQLite, `tmp_path`,
  `Base.metadata.create_all()`, тот же стиль, что и `tests/integration/
  test_process_user_message_persistence.py`) — полный цикл через
  `build_conversation_repositories_factory()`, отсутствующий пользователь
  не создаёт строк в БД, после `StartNewConversation` для пользователя в
  таблице `conversations` ровно одна активная и одна закрытая запись
  (`uq_conversations_active_user` не нарушен — секундный второй активный
  диалог никогда не существовал одновременно со старым, т.к. `close()`
  предшествует `save()` в одной транзакции), повторные вызовы сохраняют
  ровно один активный диалог, история старого (закрытого) диалога
  (сообщения, сохранённые до вызова `StartNewConversation` напрямую через
  `repositories.messages.save()`) остаётся читаемой через
  `MessageRepository.history()` после закрытия — диалог закрыт, но
  сообщения не тронуты. `grep -rn "sqlalchemy\|telegram" -i src/dekoder/
  application/conversation/use_cases/start_new_conversation.py` — совпадения
  только в докстринге (утверждения об отсутствии зависимости), не в коде;
  `MessageRepository`/Unit of Work/Generic Service не введены; 293
  теста, ruff/ruff format/mypy проходят.

**Спринт 2, S2-08 — подключение команды `/new` в Telegram Adapter
(без изменений `StartNewConversation`/`ProcessUserMessage`/
`TextMessageHandler` — подтверждено `git diff`, пустой на всех трёх
файлах):**

* `src/dekoder/presentation/telegram/handlers/new_conversation.py`
  (новый файл) — класс `NewConversationHandler`, конструктор принимает
  единственную зависимость `start_new_conversation: StartNewConversation`
  (dependency injection, тот же стиль, что и `TextMessageHandler`).
  `__call__`: если `update.effective_message is None` — выйти; иначе
  построить команду через `mapper.py::to_start_new_conversation_command`,
  вызвать `start_new_conversation.execute()`, поймать `DekoderError`
  отдельно от прочих исключений (тот же паттерн, что и `TextMessageHandler`)
  и отправить пользователю текстовый ответ. `result.conversation_id is
  None` (пользователь никогда не общался с ботом — `StartNewConversation`
  не создаёт его автоматически, S2-07) → нейтральное сообщение
  `NO_PREVIOUS_INTERACTION_MESSAGE`, без ошибки; иначе →
  `NEW_CONVERSATION_STARTED_MESSAGE`. Никакой бизнес-логики (закрытие/
  создание диалога полностью внутри `StartNewConversation.execute()`), не
  импортирует SQLAlchemy, ORM-модели или репозитории — подтверждено
  тестом на AST-разбор импортов (см. ниже);
* `src/dekoder/presentation/telegram/mapper.py` — добавлена
  `to_start_new_conversation_command(update) -> StartNewConversationCommand`,
  тот же принцип, что и `to_command()`: единственное место, извлекающее
  `telegram_user_id` из `update.effective_user.id` для обработчика `/new`;
* `src/dekoder/presentation/telegram/bot.py` — добавлена
  `register_new_conversation_handler(application, start_new_conversation)`,
  по образцу `register_message_handler` — тоже вызывается только после
  того, как зависимость use case собрана (см. `telegram_main.py`), не
  внутри `build_telegram_application()`, т.к. `StartNewConversation`
  требует `ConversationRepositoriesFactory`, которая требует БД;
* `src/dekoder/bootstrap/container.py` — `ApplicationContainer` получил
  новое поле `start_new_conversation: StartNewConversation`;
  `build_container()` собирает `StartNewConversation(repositories=
  repositories_factory)` поверх ТОЙ ЖЕ `repositories_factory`, что уже
  использует `ProcessUserMessage` — не вторая, параллельная фабрика;
* `src/dekoder/telegram_main.py` — внутри `post_init` (`_startup`) после
  `register_message_handler(...)` добавлен вызов
  `register_new_conversation_handler(app, container.start_new_conversation)`,
  в том же event loop'е, что и БД/`ProcessUserMessage`. Только Telegram
  polling-процесс — `/new` в FastAPI-приложении (`main.py`,
  `bootstrap/application.py`) не регистрируется: команда — Telegram-специфичная
  сущность, `get_process_user_message()`-подобная FastAPI-зависимость для
  `StartNewConversation` не добавлялась, т.к. никакой FastAPI route её не
  использует (YAGNI, backlog_2.md §15, инвариант 14);
* тесты: `tests/unit/presentation/telegram/test_new_conversation_handler.py`
  (новый) — `StartNewConversation` собирается по-настоящему поверх
  in-memory fake-репозиториев (`tests/support/
  fake_conversation_repositories.py`, тот же helper, что и у
  `TextMessageHandler`/`ProcessUserMessage`), обёрнут spy'ем
  `RecordingStartNewConversation` для проверки переданных аргументов;
  покрывает: неизвестный пользователь (нейтральное сообщение, без
  исключения, диалог не создаётся), пользователь без активного диалога
  (новый диалог создаётся, подтверждение отправлено), пользователь с
  активным диалогом (старый закрывается, новый — единственный активный,
  подтверждение отправлено), корректная передача `telegram_user_id` в
  `StartNewConversationCommand`, `Update` без сообщения игнорируется,
  `DekoderError`/неожиданное исключение → безопасное сообщение (тот же
  паттерн, что и `test_messages_handler.py`), и архитектурная проверка
  `TestNoDirectRepositoryOrOrmAccess` — разбирает `new_conversation.py`/
  `bot.py` через `ast.parse` и проверяет отсутствие импортов, начинающихся
  с `sqlalchemy`/`dekoder.infrastructure` (через AST, а не поиск подстроки
  в тексте файла — докстрings этих модулей упоминают «SQLAlchemy»/
  «AsyncSession» словами, поясняя их отсутствие, что дало бы ложное
  срабатывание при простом `"sqlalchemy" in source`); 306 тестов,
  ruff/ruff format/mypy проходят.

**Спринт 2, S2-09 — `ClearConversation` use case (Application Layer;
подключение команды `/clear` к Telegram Adapter — следующая задача
Sprint 2, S2-10; `ProcessUserMessage`/`StartNewConversation`/
`NewConversationHandler` не изменены — подтверждено `git diff`, пустой на
всех трёх файлах):**

* `src/dekoder/application/conversation/dto.py` — добавлены
  `ClearConversationCommand` (`telegram_user_id: int`, тот же минимальный
  состав, что и `StartNewConversationCommand`), `ClearConversationStatus`
  (`Enum`: `CLEARED`/`ALREADY_EMPTY`/`NO_ACTIVE_CONVERSATION` — тот же
  стиль, что и доменный `MessageRole`) и `ClearConversationResult`
  (`status: ClearConversationStatus`, `conversation_id: UUID | None`,
  `deleted_count: int`) — три поля вместе однозначно различают все три
  исхода задачи, а не только `conversation_id is None`, как у
  `StartNewConversationResult`: диалог активен, но пуст
  (`ALREADY_EMPTY`), должен отличаться от диалога, который был очищен
  (`CLEARED`), хотя оба сохраняют один и тот же `conversation_id` и
  `deleted_count`/`0` по отдельности это не различает. Изменение в
  `dto.py` строго аддитивно — существующие `StartNewConversation*`/
  `ProcessUserMessage*` типы не тронуты (подтверждено `git diff`);
* `src/dekoder/application/conversation/use_cases/clear_conversation.py`
  (новый файл) — класс `ClearConversation`, конструктор принимает
  единственную зависимость `repositories: ConversationRepositoriesFactory`
  (тот же порт, что и `StartNewConversation`/`ProcessUserMessage`) — не
  принимает `LLMProvider` вовсе (архитектурный факт, не просто «не
  вызывается»: параметра в сигнатуре `__init__` нет, проверено unit-тестом
  через `inspect.signature`). `execute()` — один короткий `async with
  self._repositories()` блок (LLM не вызывается, разделять транзакцию не
  требуется, как и у `StartNewConversation`): находит пользователя через
  `users.get_by_telegram_user_id()` (не `get_or_create...` — пользователь
  не создаётся автоматически), затем активный диалог через
  `conversations.get_active_by_user_id()` (не `get_or_create_active` —
  диалог не создаётся автоматически); при отсутствии пользователя ИЛИ
  диалога возвращает `NO_ACTIVE_CONVERSATION` без побочных эффектов; иначе
  вызывает ровно один метод — `messages.clear(active_conversation.id)` — и
  по возвращённому числу удалённых строк выбирает `CLEARED` (>0) или
  `ALREADY_EMPTY` (0). `repositories.conversations.save()`/`.close()` не
  вызываются НИ РАЗУ в этом файле — `Conversation`, найденный через
  `get_active_by_user_id`, дальше никак не передаётся ни в один из этих
  методов (в контракте `ConversationRepository` метода удаления диалога не
  существует вовсе — удалить диалог этим use case физически нечем);
* тесты: `tests/unit/application/test_clear_conversation.py` (новый,
  11 тестов) — in-memory fake-репозитории
  (`tests/support/fake_conversation_repositories.py`, тот же helper, что и
  у `StartNewConversation`/`ProcessUserMessage`), обёрнутые
  `SpyConversationRepository`/`SpyMessageRepository` для подтверждения
  фактического ОТСУТСТВИЯ вызова `.save()`/`.close()` (не только
  результирующего состояния) и точного аргумента `.clear()`; покрывает:
  отсутствующего пользователя, пользователя без активного диалога,
  активный диалог с сообщениями (`CLEARED`, верный `conversation_id`
  передан в `.clear()`), уже пустую историю (`ALREADY_EMPTY`, отличим от
  `NO_ACTIVE_CONVERSATION`), повторную очистку пустой истории без
  исключения, диалог не удаляется/не закрывается/не создаётся заново,
  отсутствие `LLMProvider` в сигнатуре конструктора;
  `tests/integration/test_clear_conversation_persistence.py` (новый,
  9 тестов) — реальные SQLAlchemy-репозитории поверх временной SQLite
  (`tmp_path`, тот же стиль, что и `test_start_new_conversation_persistence.py`);
  покрывает: история пуста после очистки и диалог остаётся существующим и
  активным (`closed_at is None`), следующее сообщение после очистки
  сохраняется в том же `conversation_id`, сообщения другого пользователя и
  сообщения другого (закрытого) диалога того же пользователя не
  затрагиваются, отсутствующий пользователь/диалог не создают и не меняют
  ничего в БД; 326 тестов, ruff/ruff format/mypy проходят.

**Спринт 2, S2-10 — подключение команды `/clear` в Telegram Adapter
(последняя функциональная задача Sprint 2; `ClearConversation`/
`ProcessUserMessage`/`StartNewConversation`/`TextMessageHandler`/
`NewConversationHandler` не изменены по существу — подтверждено `git diff`,
пустой на всех пяти файлах):**

* `src/dekoder/presentation/telegram/handlers/clear_conversation.py`
  (новый файл) — `ClearConversationHandler`, тот же стиль, что и
  `NewConversationHandler`: конструктор принимает единственную зависимость
  `ClearConversation` (dependency injection), `__call__` извлекает команду
  через `mapper.py::to_clear_conversation_command`, вызывает
  `execute()`, оборачивает вызов в `try/except DekoderError`/`except
  Exception` (тот же паттерн, что и `NewConversationHandler`/
  `TextMessageHandler`). Все три значения `ClearConversationResult.status`
  переводятся в три РАЗНЫХ константы-сообщения модуля
  (`CONVERSATION_CLEARED_MESSAGE`/`CONVERSATION_ALREADY_EMPTY_MESSAGE`/
  `NO_ACTIVE_CONVERSATION_MESSAGE`) через словарь `_STATUS_MESSAGES` —
  тексты не хранятся в use case;
* `src/dekoder/presentation/telegram/mapper.py` — добавлена
  `to_clear_conversation_command(update) -> ClearConversationCommand`,
  дословно тот же принцип, что и `to_start_new_conversation_command()`
  (извлекает `telegram_user_id` из `update.effective_user.id`,
  `ValueError` при отсутствующем пользователе);
* `src/dekoder/presentation/telegram/bot.py` — добавлена
  `register_clear_conversation_handler(application, clear_conversation)`,
  регистрирует `CommandHandler("clear", ClearConversationHandler(...))`,
  тем же стилем, что и `register_new_conversation_handler`;
* `src/dekoder/bootstrap/container.py` — `ApplicationContainer` получил
  поле `clear_conversation: ClearConversation`; `build_container()`
  собирает `ClearConversation(repositories=repositories_factory)` поверх
  ТОЙ ЖЕ `repositories_factory`, что уже используют `ProcessUserMessage`/
  `StartNewConversation` — вторая фабрика не создаётся;
* `src/dekoder/telegram_main.py` — `_startup`/`post_init` вызывает
  `register_clear_conversation_handler(app, container.clear_conversation)`
  сразу после `register_new_conversation_handler` (тот же порядок
  рассуждений про event loop/`aiosqlite`, что и у `/new`, S2-08);
* тесты: `tests/unit/presentation/telegram/test_clear_conversation_handler.py`
  (новый) — `ClearConversation` собирается по-настоящему поверх in-memory
  fake-репозиториев (`tests/support/fake_conversation_repositories.py`);
  покрывает все три статуса своим отдельным сообщением, точную передачу
  `telegram_user_id`, однократный вызов use case, `Update` без сообщения
  игнорируется, `DekoderError`/неожиданное исключение → безопасное
  сообщение (тот же паттерн, что и `test_new_conversation_handler.py`), и
  архитектурную проверку `TestNoDirectRepositoryOrOrmAccess` (AST-разбор
  `clear_conversation.py` — отсутствие импортов `sqlalchemy`/
  `dekoder.infrastructure`); `tests/unit/presentation/telegram/
  test_mapper.py` — расширен тестами `to_clear_conversation_command`;
  `tests/e2e/test_conversation_scenario.py` — расширен классом
  `TestClearCommandRouting`: реальный `telegram.ext.Application` с
  зарегистрированными `/clear` (`CommandHandler`) и обычным текстовым
  обработчиком (`MessageHandler`) поверх ОДНИХ И ТЕХ ЖЕ in-memory
  fake-репозиториев — подтверждает, что callback `/clear` отличается от
  callback обычных сообщений, что вызов `/clear` не обращается к
  `LLMProvider`, что `/clear` реально удаляет историю, сохраняя тот же
  `conversation_id` активным, и что следующее обычное сообщение после
  `/clear` продолжается в том же диалоге (маршрутизацию `CommandHandler`
  vs `MessageHandler` внутри `telegram.ext.Application` самой библиотеки
  тест не проверяет — уже проверено python-telegram-bot, см. докстринг
  файла); 346 тестов, ruff/ruff format/mypy проходят.

**Спринт 2, S2-11 — финальная интеграция и E2E-проверка (последняя
задача Sprint 2; аудит composition root/DI/транзакций/конфигурации/
миграций — новая бизнес-функциональность не добавлялась):**

Аудит перед изменениями показал, что composition root (`bootstrap/
container.py`/`repositories.py`/`database.py`) и все Telegram-хендлеры
(S2-01…S2-10) уже были корректно связаны: три use case собираются поверх
одной `repositories_factory`, хендлеры не создают `AsyncSession`/
репозитории напрямую, `filters.TEXT & ~filters.COMMAND` не пускает
команды в текстовый обработчик, транзакционные границы `ProcessUserMessage`
уже разделяли сохранение user message/чтение истории/вызов LLM/сохранение
assistant message на три независимых коротких транзакции (см. S2-06).
Архитектурных изменений это не потребовало. Найдено и точечно исправлено
три реальных интеграционных дефекта, ни один не архитектурный:

* `src/dekoder/application/conversation/use_cases/process_user_message.py`
  — `_build_message` (`@staticmethod` → метод экземпляра) теперь хранит
  `_last_message_created_at` и гарантирует строго возрастающий `created_at`
  в рамках одного экземпляра `ProcessUserMessage` (singleton на процесс).
  Причина: на этой машине (Windows) `datetime.now(UTC)`, вызванная дважды
  подряд без реального I/O между вызовами, стабильно возвращает ОДНО и то
  же значение (проверено вручную — 20 последовательных вызовов в цикле
  дали нулевую разницу), а `MessageRepository.history()` сортирует
  `created_at ASC, id ASC` (S2-05) — вторичный ключ `id` случаен (`uuid4`)
  и не связан с порядком создания. При совпадении `created_at` порядок
  `user`/`assistant` в истории и в запросе к LLM становился недетерминирован
  — новый e2e-тест (см. ниже) воспроизводимо падал на этом (~30–40% прогонов
  до фикса, 0 из ~15 прогонов после). Исправление — только в Application
  Layer, без изменений ORM/схемы/репозиториев/S2-05 (эта задача уже была
  провалидирована и протестирована отдельно, переписывать её незачем —
  дефект был не в тай-брейке самом по себе, а в отсутствии гарантии
  различающихся `created_at` со стороны вызывающего кода);
* `Dockerfile` — непривилегированный `dekoder` не мог создать `/app/data`
  (`bootstrap/database.py::_ensure_sqlite_directory_exists`, S2-01):
  `/app` создаётся `WORKDIR`/`COPY` от имени `root` ещё до `USER dekoder`,
  без явного `chown` `mkdir` от `dekoder` падал `Permission denied` — оба
  сервиса (`api`/`telegram-bot`) не проходили бы `init_database()` при
  старте. Подтверждено вручную: `docker build` + `docker run ... mkdir
  /app/data` от лица `dekoder` падал до фикса, после — `RUN mkdir -p
  /app/data && chown -R dekoder:dekoder /app/data` (до `USER dekoder`)
  проходит, `docker run` реального образа успешно поднимает `uvicorn` и
  отвечает `200` на `/health`;
* `docker-compose.yml` — ни `api`, ни `telegram-bot` не монтировали
  `/app/data` ни в один volume: SQLite-файл жил только в writable-слое
  контейнера и терялся при любом `docker compose down`/пересборке образа
  — прямое нарушение цели Sprint 2 («постоянное хранилище») в реальном
  Docker-развёртывании (тестовые сценарии этого не ловят — используют
  временную SQLite напрямую, не Docker). Добавлен общий именованный volume
  `dekoder_data:/app/data` для обоих сервисов (SQLite штатно поддерживает
  несколько процессов на одном файле через файловые блокировки; отдельный
  volume на сервис создал бы два расходящихся файла без пользы, т.к.
  `telegram-bot` — единственный сейчас писатель). Подтверждено вручную:
  `docker compose up` → запись файла-пробы в `/app/data` → `docker compose
  down` (без `-v`) → `docker compose up` → файл-проба всё ещё на месте.

Добавлен `tests/e2e/test_conversation_persistence_scenario.py` (8 тестов)
— тот же харнесс, что и `tests/e2e/test_conversation_scenario.py`
(реальный `telegram.ext.Application`, реальные хендлеры/use cases,
единственная подмена — `FakeLLMProvider`), но поверх РЕАЛЬНОЙ временной
SQLite (`tmp_path`, `Base.metadata.create_all()`, то же допустимое
исключение для тестового окружения, что и в `tests/integration/
test_*_persistence.py`) вместо in-memory fake-репозиториев — покрывает
восемь обязательных сценариев backlog_2_tasks.md (S2-11), которых не было
ни в одном существующем тесте в таком сочетании (Telegram-слой + реальная
БД + маршрутизация команд одновременно): первый и второй запрос одного
пользователя (роли `user, assistant, user, assistant`, физическая проверка
через прямой `SELECT` по `UserORM`/`ConversationORM`/`MessageORM`), `/new`
(старый диалог закрыт, новый активен, старые сообщения читаемы),
`/clear` (история физически удалена, тот же `conversation_id` остаётся
активным), изоляция двух `telegram_user_id` (раздельные `Conversation`,
не смешанные `Message`), перезапуск приложения (`AsyncEngine.dispose()` →
новый `AsyncEngine`/`async_sessionmaker`/`ConversationRepositoriesFactory`
поверх ТОГО ЖЕ файла SQLite → данные на месте, диалог продолжается тем же
`conversation_id`), ошибка LLM (user message сохранён, assistant
отсутствует, следующий запрос успешен), ошибка БД (искусственный сбой
`MessageRepository.save()` — обёртка вокруг настоящего `SQLAlchemyMessageRepository`
внутри тестового варианта `build_conversation_repositories_factory`,
`_make_faulty_repositories_factory` — поднимает исключение до реальной
записи; LLM не вызывается, сообщение не сохранено — настоящий
`session_scope()` реально откатывает транзакцию, а не in-memory fake;
следующий корректный запрос через `build_conversation_repositories_factory`
поверх той же `session_factory` проходит штатно).

`README.md` обновлён под фактическое состояние Sprint 2 (было — только
S2-01, без таблиц): раздел «Что реально работает сейчас» описывает
персистентность и `/new`/`/clear`, дерево каталогов — `domain/user`,
`application/user`, полный список `infrastructure/persistence/`,
`presentation/telegram/handlers/`; раздел «База данных и миграции»
описывает реальную схему (`users`/`conversations`/`messages`, `alembic
check`), добавлена инструкция применить миграции перед первым запуском;
раздел «Тесты» упоминает оба e2e-файла.

Проверено и НЕ изменено (уже корректно на момент начала S2-11, подтверждено
тестами/вручную, изменений не потребовалось): `PRAGMA foreign_keys=ON`
включён централизованно (`infrastructure/persistence/engine.py`,
подтверждено `PRAGMA foreign_keys` → `1` на живом соединении);
`alembic upgrade head` на пустой БД, повторный `upgrade head`, `downgrade
-1` → `upgrade head`, `alembic check` — все без ошибок и без расхождений
схемы; `DATABASE_URL` читается только через `DatabaseSettings`
(`shared/config.py`), не хардкожен; `.env.example` содержит `DATABASE_URL`
без секретов; SQLAlchemy не импортируется в `domain/`/`application/`
(`grep`, только докстринги); ORM/`AsyncSession`/`infrastructure.persistence`
не импортируются в `presentation/telegram/` (`grep`); Telegram-хендлеры
не создают репозитории/сессии напрямую — все зависимости приходят через
конструктор из `bootstrap/container.py`. 354 теста (346 + 8 новых
e2e), ruff/ruff format/mypy проходят.

## В разработке

Ничего — Sprint 8 полностью завершён (S8-01…S8-11, см. запись в §32
«Текущий спринт (обновление 6)» и запись в конце этого раздела).
Следующий шаг — Этап 11 (полноценный просмотр логов/метрик,
`AccessDeniedError`/`ConfigurationError`/`KnowledgeSearchError`,
сквозной `correlation_id`), не начат.

## Не реализовано

* Prompt Engine (Этап 6) реализован в Sprint 4; долговременная память
  (Этап 7) — в Sprint 5; база знаний и RAG (Этап 8) — в Sprint 6; выбор
  AI-модели (Этап 9) — в Sprint 7; административные функции (Этап 10,
  admin REST для документов/профилей, реальный health-check) — в Sprint 8
  (см. запись выше) — ни одна из этих секций/возможностей больше не
  относится к «не реализовано». `CreateProfile`/`UpdateProfile`/
  `DeactivateProfile` (персональные, каталожные профили-CRUD) реализованы
  в Sprint 8 (S8-06/S8-07/S8-08), не персональные профили пользователя
  (те по-прежнему не входят в модель Sprint 1-8 — каталог общий,
  ADR-3.1).
* полноценный просмотр/агрегация логов и метрик, полная иерархия ошибок
  §17.4 «Плана реализации.md» (`AccessDeniedError`/`ConfigurationError`/
  `KnowledgeSearchError`, сквозной `correlation_id` через весь стек) —
  Этап 11, явно отложено пользователем на этапе планирования Sprint 8
  (backlog_8.md §1, скоуп-решение №3); Sprint 8 добавил ровно один новый
  класс, `NotFoundError`, и аудит-логирование административных действий
  через уже существующий `structlog`, не полноценную подсистему логов.
* admin CRUD каталога AI-моделей (`admin_models.py`, §16.5 «Плана
  реализации.md»), admin-управление долговременной памятью
  (`MemoryRecord` cross-user list/delete) — явно отклонены пользователем
  на этапе планирования Sprint 8 (backlog_8.md §1, скоуп-решения №2/№3);
  каталог моделей остаётся статичным `catalog.json` четвёртый спринт
  подряд (Sprint 5-8).
* `UpdateMemoryRecord` (§13.6 «Плана реализации.md») — сознательно не
  реализован в Sprint 5 (ADR-5.9, S5-05): нет вызывающего сценария без
  административного интерфейса (Этап 10). `ConfirmMemoryRecord`/
  `RejectMemoryRecord` реализованы полноценно, но не подключены к
  Telegram — нет двухшагового подтверждаемого сценария в MVP (ADR-5.9).
* команда `/forget` (упомянута §13.6 «Плана реализации.md») — заменена
  inline-удалением в `/memory` (ADR-5.10), сознательно не реализована.
* векторный поиск по памяти (§13.7 «Плана реализации.md»: «может быть
  добавлен позднее») — Sprint 5 использует только простой SQL-фильтр
  (ADR-5.6).
* реальные прямые (не через OpenRouter) адаптеры провайдеров
  (`OpenAIAdapter`/`YandexGPTAdapter`/`AnthropicAdapter`/`GeminiAdapter`/
  `OllamaAdapter`, §15.6) и интеллектуальная авто-маршрутизация между
  моделями (§15.5) — явно отложены Sprint 7 (backlog_7.md §1, «В Sprint 7
  не входят») до стабилизации интерфейса; каталог моделей и персональный
  выбор (Этап 9) полностью реализованы и не входят в этот список.
* редактирование каталога моделей через Telegram/HTTP, CRUD каталога —
  сознательно не реализовано ни в Sprint 7 (ADR-7.4), ни в Sprint 8
  (скоуп-решение №2, см. запись выше): каталог остаётся статичным файлом,
  правится передеплоем.
* `UserProfile.preferred_model` — по-прежнему не читается/не пишется
  (ADR-7.6, третий спринт подряд): персональный выбор модели моделируется
  исключительно через `ModelSelection`/`user_active_models`, не через это
  поле — сознательно не «реализовано» в терминах Sprint 7, задел на
  гипотетическую будущую семантику «эта персона рекомендует эту модель».

## Известные расхождения

**В репозитории одновременно существуют два несовместимых дерева
исходного кода.** До прочтения этого файла (в той же сессии) была
выполнена большая, отдельная миграция по `docs/versions/*_v2.0.md`:
`composition/`, `interfaces/`, `domain/`/`application/`-модули `ai_core`,
`admin`, `memory`, `knowledge_base`, `rag`, `model_catalog`, `logging`,
LLM-адаптеры под `infrastructure/model_gateway/` — почти 200
файлов-заглушек (`raise NotImplementedError`), построенных по архитектуре,
отличной от этого файла (`interfaces/`+`composition/`, не
`presentation/`+`bootstrap/`).

Осознанное решение пользователя: **не реконсилировать сейчас** —
Спринт 1 продолжает строиться по этому файлу (`bootstrap/`,
`application/conversation/`, `domain/conversation/`,
`infrastructure/llm/`), старое дерево остаётся нетронутым, но не
используется реально запускаемым приложением (`main.py` уже указывает
на новый `bootstrap/`). Собственные тесты старого дерева по-прежнему
проходят (`tests/integration/test_health_endpoint.py` тестирует
`composition.bootstrap.create_app()` напрямую) — они не сломаны, просто
не то, что реально исполняется.

Конкретное дублирование, которое стоит держать в уме: `ModelId`
существует дважды (`shared/domain/identifiers.py` — старый `NewType`
без валидации; `domain/conversation/value_objects.py` — новый,
валидируемый, используется этим срезом). Абстракция вызова LLM тоже
задублирована: `application/model_gateway/ports.py::ModelGateway`
(старое дерево, sync, TEXT/IMAGE) и `application/conversation/
ports.py::LLMProvider` (этот срез, async, только текст, реально
используется).

Реконсиляция (удалить/переименовать одно из деревьев, объединить порты)
— решение, которое нужно принимать явно и отдельно, не молча, когда
до него дойдёт очередь (см. §31).

**Обновление Sprint 4 (S4-01, ADR-4.10):** два узла старого дерева,
релевантных Sprint 4, удалены — `infrastructure/logging/`/
`application/logging/*`/`domain/logging/*` (не используемый реальными
composition root'ами v2.0-логгер — прямой риск путаницы для требования
«версия шаблона в метаданных ответа») и `application/prompt_engine/`/
`application/ai_core/internal_services/prompt_assembler.py` (нерабочий
«второй построитель промпта» ровно в момент, когда строился настоящий
Prompt Engine). Остальной v2.0-скелет (`admin`, `memory`, `rag`,
`session`, `skills`, `model_catalog`, `knowledge_base`, `model_gateway`,
`infrastructure/vector_storage`, `interfaces/`, `composition/`) не
тронут — признан нежизнеспособным той же логикой, но его зачистка
осознанно вынесена в отдельную будущую задачу (ADR-4.10), не в Sprint 4.

**Обновление Sprint 5 (S5-01, ADR-5.1):** узел памяти старого дерева,
релевантный Sprint 5, удалён — `application/memory/*` (порт
`MemoryRepository` со старой формой `record_message`/
`stage_fact_draft`/`confirm_fact_draft`/`forget_fact`, use cases,
все `raise NotImplementedError`), `domain/memory/*` (`DialogueEntry`,
`MemoryFact`, `MemoryFactDraft` — простые `@dataclass`, без `frozen`/
`slots`/валидации), `infrastructure/persistence/
sqlite_memory_repository.py`, `application/ai_core/internal_services/
memory_collector.py` — та же логика, что ADR-4.10: правдоподобно
выглядящий «модуль памяти» ровно в момент, когда строился настоящий
(структурно другая модель предметной области — диалог+черновик факта,
не `MemoryRecord`). Точечная зачистка dangling-импортов затронула не
только `composition/container.py` (буквально названный в тексте
задачи), но и четыре файла `application/ai_core/`/`shared/application/
execution_context.py`, транзитивно импортировавших удаляемые типы —
задокументировано как отклонение от буквального текста задачи в §32
(S5-01) и в сообщении коммита. Остальной v2.0-скелет (`admin`, `rag`,
`session`, `skills`, `model_catalog`, `knowledge_base`, `model_gateway`,
`infrastructure/vector_storage`, `interfaces/`, `composition/` за
пределами точечной правки) не тронут — признан нежизнеспособным той же
логикой, зачистка осознанно вынесена в отдельную будущую задачу
(ADR-4.10/ADR-5.1), не в Sprint 5. `shared/domain/identifiers.py`
по-прежнему не тронут — его `DialogueEntryId` остаётся единственным
ожидаемым grep-хитом старой формы имён в `src`/`tests`.

**Обновление Sprint 6 (не задокументировано отдельно в момент
выполнения):** судя по коммитам `feature/sprint-6` (S6-01), узел
`knowledge_base`/`rag`/`admin` старого дерева, релевантный базе знаний,
тоже удалён той же логикой (ADR-6.x) — не проверено этой сессией
детально (Sprint 7 не трогает базу знаний/RAG), см. примечание об
отсутствующей записи Sprint 6 в §32 выше.

**Обновление Sprint 7 (S7-01, ADR-7.1):** узел каталога моделей
старого дерева, релевантный Sprint 7, удалён —
`domain/model_catalog/model_definition.py` (`ModelDefinition` — плоский
dataclass), `application/model_catalog/*` (`ModelCatalogRepository` со
старой формой `list_compatible(skill_id, generation_type)`, use case
`GetAvailableModelsUseCase`), `application/model_gateway/ports.py::
ModelGateway`, `infrastructure/model_gateway/*`,
`infrastructure/persistence/sqlite_model_catalog_repository.py` — та же
логика, что ADR-4.10/5.1/6.x: правдоподобно выглядящий «каталог
моделей» ровно в момент, когда строился настоящий (структурно другая
модель — плоский `ModelDefinition`, не `AIModel`/`AIProvider`/
`ModelCapability`/`ModelAvailability`/`GenerationSettings`; использует
мёртвый `ModelId` из `shared/domain/identifiers.py`, не живой
`domain/conversation/value_objects.ModelId`). Точечная зачистка
dangling-импортов затронула не только `composition/container.py`
(буквально названный в тексте задачи), но и четыре файла мёртвого
`application/ai_core/` (`internal_services/{model_selector,
response_formatter}.py` удалены целиком — та же логика, что
`knowledge_collector.py` в S6-01 — и `use_cases/{generate_content,
route_command}.py`, лишившиеся только относящихся к каталогу
параметров/методов) — задокументировано как отклонение от буквального
текста задачи в §32 (S7-01) и в сообщении коммита. Остальной
v2.0-скелет (`admin`, `rag`, `session`, `skills`, `knowledge_base`,
`interfaces/`, `composition/` за пределами точечной правки) и живой
`domain/user`/`application/user` не тронуты — зачистка остального
скелета осознанно вынесена в отдельную будущую задачу (ADR-4.10/5.1/
6.x/7.1), не в Sprint 7. `shared/domain/identifiers.py` по-прежнему не
тронут.

**Новая, актуальная после Sprint 7 запись про два несовместимых
`ModelId`** (см. абзац «Конкретное дублирование…» выше, писавшийся ещё
в Sprint 1): `application/model_gateway/ports.py::ModelGateway` и
дублирующий `ModelId` из `shared/domain/identifiers.py`, упомянутые там
как часть старого дерева — теперь оба физически удалены (S7-01,
ADR-7.1/7.2, узел `model_gateway` целиком, узел `model_catalog`
целиком). Абзац оставлен как есть (не переписан) — он верно описывает
состояние на момент Sprint 1 и объясняет ИСТОРИЮ дублирования; удаление
конкретных файлов, о которых он предупреждал, зафиксировано здесь, а не
через правку задним числом более раннего текста.

**Обновление Sprint 8 (S8-01, ADR-8.1):** узел администрирования
старого дерева, релевантный Sprint 8, удалён — `application/admin/`
(`ports.py::AdminAuthPort`, `commands.py::AuthenticateAdminCommand`,
`use_cases/authenticate_admin.py::AuthenticateAdminUseCase` —
login/session/токен-модель, `raise NotImplementedError`) — та же логика,
что ADR-4.10/5.1/6.x/7.1: правдоподобно выглядящий «модуль
администрирования» ровно в момент, когда строился настоящий (структурно
другая модель авторизации — статичный API-key, не login/password/
session, скоуп-решение пользователя №1). В отличие от S5-01/S7-01, здесь
dangling-импорт был не в `application/ai_core/` (это про каталог
моделей), а в самом `composition/container.py::Container` — датакласс
держал поля `admin_auth: AdminAuthPort`/`authenticate_admin:
AuthenticateAdminUseCase`, импортированные на уровне модуля; удаление
`application/admin/` без правки `composition/container.py` сломало бы
импорт этого модуля, а с ним — транзитивно импортирующий его
`composition/bootstrap.py::create_app`, используемый живым, проходящим
тестом (`tests/integration/test_health_endpoint.py`). Задокументировано
как отклонение от буквального текста задачи (та ограничивала правку
только удалением `application/admin/`) в §32 (S8-01) и в сообщении
коммита. Остальной v2.0-скелет (`rag`, `session`, `skills`,
`knowledge_base`, `interfaces/`, `shared/domain/identifiers.py`,
`composition/` за пределами точечной правки) не тронут — зачистка
остального скелета осознанно вынесена в отдельную будущую задачу
(ADR-4.10/5.1/6.x/7.1/8.1), не в Sprint 8.

## Последнее принятое решение

Уточнена формулировка §8.5/§18: «bootstrap» — роль (единственная точка
сборки Settings и зависимостей), а не только каталог `bootstrap/`;
`main.py`/`telegram_main.py` как тонкие entry-point файлы входят в эту
роль. Код не менялся — `Settings()` по-прежнему создаётся в entry-point
файлах и передаётся параметром в `bootstrap.application.create_application`/
`bootstrap.container.build_container`, это сознательно оставлено как
есть ради тестируемости (см. `shared/config.py`).

Спринт 1 завершён по этому файлу (`bootstrap/`,
`application/conversation/`, `domain/conversation/`,
`infrastructure/llm/`, `presentation/telegram/`); параллельное дерево
`docs/versions/*_v2.0.md`-миграции (`composition/`, `interfaces/` и
связанные модули) осталось нетронутым и не реконсилировано — решение
по-прежнему в силе, реконсиляция не предпринимается без отдельного
запроса.

S2-01 (подключение SQLAlchemy/Alembic) реализован строго как
инфраструктура, отдельно от `composition/infrastructure/persistence/
sqlite_*.py` (мёртвое дерево, старые sync-репозитории — не тронуты,
новые async-файлы добавлены в тот же каталог `infrastructure/
persistence/`, но не конфликтуют по именам). Engine — bootstrap-singleton
(создаётся в `bootstrap/database.py`, не в use case и не в Telegram-слое);
для `telegram_main.py` инициализация вынесена в `post_init`/`post_shutdown`
`Application`, а не в тело `main()` до `run_polling()` — осознанное
решение из-за привязки `aiosqlite`-соединений к event loop'у, в котором
они были открыты (`run_polling()` создаёт собственный loop).

S2-02 (доменная модель `User`/`Conversation`/`Message`, ORM, mapper,
первая миграция) реализован строго в границах задачи: без репозиториев,
без Unit of Work, без изменений `ProcessUserMessage`/`/new`/`/clear` —
следующая задача Sprint 2 (S2-03). `User` получил собственный подпакет
`domain/user/` (не внутри `domain/conversation/`), поскольку не входит
в агрегат `Conversation` (ADR-2.3, backlog_2.md §6 «Границы агрегатов»);
`Conversation`/`Message`/`MessageRole` — рядом с существующим
`domain/conversation/value_objects.py`. ORM-модели — без `relationship()`
(осознанно: доступ к диалогам/сообщениям будет через репозитории S2-03,
не через ORM-навигацию — исключает случайную загрузку всей истории и
избавляет от соблазна использовать ORM-каскады вместо явной реализации
`/clear`). Частичный уникальный индекс на активный диалог пользователя
— единственная защита инварианта на уровне БД, подтверждена
интеграционным тестом (падает `IntegrityError`, не молча). ORM-моделей
`sqlite_*.py` (мёртвое дерево) снова не касались.

S2-03 (`UserRepository`) реализован строго в границах задачи: только
пользователи, без `ConversationRepository`/`MessageRepository`, без
Unit of Work/Generic Repository, без изменений `ProcessUserMessage`/
`/new`/`/clear` — следующая задача Sprint 2 (S2-04). Порт получил
собственный подпакет `application/user/` (не внутри
`application/conversation/`, где лежит `LLMProvider`) — по аналогии с
`domain/user/` из S2-02, `User` не входит в агрегат `Conversation`.
Гонка при `get_or_create_by_telegram_user_id()` разрешается исключительно
уникальным ограничением БД `uq_users_telegram_user_id` (S2-02): вторая из
двух конкурентных транзакций падает `IntegrityError` на `commit()`,
откатывается и повторно находит запись, созданную первой — подтверждено
интеграционным тестом с `asyncio.gather()` на двух независимых
`AsyncSession`. `IntegrityError` не считается автоматически доказательством
гонки — проверяется, что это именно нарушение `uq_users_telegram_user_id`
(по подстроке в `exc.orig`), иначе ошибка пробрасывается как
`InfrastructureError`, не глотается молча. Отдельный `DuplicateUserError`
не создан — `get_or_create` разрешает конфликт сам, как и требовала
задача. Bootstrap-фабрика (`bootstrap/repositories.py`) подготовлена, но
сознательно не подключена ни в `ApplicationContainer`, ни в
`ProcessUserMessage` — это явная граница задачи S2-03, а не забытое
подключение (см. `## Не реализовано` выше). ORM-моделей `sqlite_*.py`
(мёртвое дерево) снова не касались.

S2-04 (`ConversationRepository`) реализован строго в границах задачи:
только диалоги, без `MessageRepository`, без Unit of Work/Generic
Repository, без изменений `ProcessUserMessage`/`/new`/`/clear` —
следующая задача Sprint 2 (S2-05). Порт добавлен рядом с `LLMProvider` в
`application/conversation/ports.py` (не в отдельном подпакете, как
`UserRepository`) — по аналогии с тем, куда S2-02 положил доменную
сущность (`domain/conversation/entities.py`, не `domain/user/`):
`Conversation` входит в conversation-агрегат (ADR-2.3). Гонка при
`get_or_create_active()` разрешается исключительно уникальным
ограничением БД `uq_conversations_active_user` (S2-02), тем же способом,
что и у `UserRepository.get_or_create_by_telegram_user_id` (S2-03):
вторая из двух конкурентных транзакций падает `IntegrityError` на
`commit()`, откатывается и повторно находит запись, созданную первой —
подтверждено интеграционным тестом с `asyncio.gather()` на двух
независимых `AsyncSession`. `IntegrityError` не считается автоматически
доказательством гонки — проверяется подстрока `"conversations.user_id"`
в `exc.orig` (FK-нарушение даёт другое сообщение — `"FOREIGN KEY
constraint failed"`, не пересекается), иначе ошибка пробрасывается как
`InfrastructureError`, не глотается молча. `close()` обновляет
`closed_at`/`updated_at` точечно через `session.get()`, без
`session.merge()`, чтобы не перезаписать `user_id`/`created_at` —
явное архитектурное требование задачи, не стилистический выбор.
Репозиторий не проверяет существование пользователя и не вызывает
`UserRepository` — гарантию даёт внешний ключ `conversations.user_id →
users.id` (S2-02); получение/создание `User` осталось ответственностью
будущего вызывающего Use Case (S2-06). Bootstrap-фабрика
(`build_conversation_repository`, `bootstrap/repositories.py`)
подготовлена, но сознательно не подключена ни в `ApplicationContainer`,
ни в `ProcessUserMessage` — явная граница задачи S2-04, а не забытое
подключение (см. `## Не реализовано` выше). ORM-моделей `sqlite_*.py`
(мёртвое дерево) снова не касались.

S2-05 (`MessageRepository`) реализован строго в границах задачи — этим
завершены все три репозитория Sprint 2 (`UserRepository`/
`ConversationRepository`/`MessageRepository`), без изменений
`ProcessUserMessage`/`/new`/`/clear` — следующая задача Sprint 2 (S2-06).
Порт добавлен рядом с `LLMProvider`/`ConversationRepository` в
`application/conversation/ports.py` — по аналогии с `ConversationRepository`:
`Message` входит в conversation-агрегат (ADR-2.3). В отличие от
`UserRepository`/`ConversationRepository`, метод `save()` не имеет
парного `get_or_create*` — Sprint 2 не требует идемпотентного создания
сообщений (каждое сообщение создаётся один раз явным вызовом Use Case), и
метод не проверяет существование диалога — эту гарантию, как и у
`ConversationRepository` относительно `User`, даёт внешний ключ
(`messages.conversation_id → conversations.id`, S2-02), а не собственная
проверка или вызов `ConversationRepository`. `history()` возвращает
`list[Message]` в порядке `created_at ASC, id ASC` — вторичная сортировка
по `id` обязательна для детерминизма при совпадающих `created_at`;
подтверждено интеграционным тестом с искусственно равными `created_at` и
намеренно «перевёрнутыми» относительно порядка вставки `id`
(`00000000-...` вставлен вторым, но должен оказаться первым в результате).
`clear()` — одна `DELETE`-операция (`sqlalchemy.delete()`), не построчное
удаление и не ORM-каскад — `MessageORM` и так без `relationship()` (S2-02);
возвращает `CursorResult.rowcount`, приведённый через `cast()`, поскольку
`AsyncSession.execute()` типизирован как `Result[Any]`, не как
`CursorResult`, хотя во время выполнения для DML `delete()` это всегда
`CursorResult`. Bootstrap-фабрика (`build_message_repository`,
`bootstrap/repositories.py`) подготовлена, но сознательно не подключена
ни в `ApplicationContainer`, ни в `ProcessUserMessage` — явная граница
задачи S2-05, а не забытое подключение (см. `## Не реализовано` выше).
ORM-моделей `sqlite_*.py` (мёртвое дерево) снова не касались.

S2-06 (расширение `ProcessUserMessage` историей диалога) реализован
эволюционно — существующий Sprint 1 use case расширен новыми
зависимостями и этапами, второй параллельный use case или второй
LLM-порт не создавались (backlog_2.md §9, ADR-2.6). Ключевое
архитектурное решение — как передать `ProcessUserMessage` доступ к трём
уже готовым репозиториям, не давая use case знать про `AsyncSession`/
SQLAlchemy и не вводя запрещённый standalone Unit of Work
(backlog_2.md §15, инвариант 14): `ConversationRepositoriesFactory`
(`application/conversation/ports.py`) — узкий, специфичный для этого
use case тип (`Callable[[], AbstractAsyncContextManager[
ConversationRepositories]]`, `ConversationRepositories` — просто три поля
`users`/`conversations`/`messages`, без методов транзакций), а не общая
абстракция для произвольных агрегатов; конкретная реализация
(`bootstrap/repositories.py::build_conversation_repositories_factory`)
оборачивает уже существующий `session_scope()` (S2-01) — новый
механизм транзакций не введён, использован принятый. Транзакционные
границы — три коротких независимых вызова `self._repositories()`
(сохранить user message + get/create user/conversation → отдельно
прочитать историю → отдельно сохранить assistant message), а не одна
обёрнутая транзакция на весь `execute()`: так гарантируется, что (а)
LLM вызывается строго вне какой-либо открытой сессии, (б) ошибка
сохранения assistant message не откатывает уже закоммиченное user
message. `LLMRequest.user_message: MessageText` (одно сообщение) заменён
на `LLMRequest.messages: Sequence[LLMMessage]` (вся история) — это
расширение существующего порта `LLMProvider`, не новый порт;
`OpenRouterLLMAdapter` — единственная реализация — обновлена вместе с
портом, ничего провайдер-специфичного в `LLMMessage` нет (`role: str,
content: str`). `ProcessUserMessageCommand.external_user_id: str`
переименован в `telegram_user_id: int` — единственный источник значения
это и требовал (`Update.effective_user.id`), строковое промежуточное
представление не имело сохранившегося обоснования. Побочный эффект для
`telegram_main.py`/`presentation/telegram/bot.py`: `ProcessUserMessage`
теперь нельзя собрать до `init_database()`, а `init_database()` обязана
жить внутри `post_init` `run_polling()` (ограничение S2-01, event loop);
`build_telegram_application()` разделена на сборку `/start` (до
`run_polling()`) и `register_message_handler()` (внутри `post_init`,
после того как `ProcessUserMessage` готов) — минимальное изменение
composition root, продиктованное новой зависимостью use case, а не
рефакторинг ради рефакторинга. `/new`/`/clear` в этой задаче не
реализовывались и не обсуждались текстом сообщения — `ProcessUserMessage`
по-прежнему не анализирует, является ли сообщение командой управления
диалогом (backlog_2.md §9, «Отдельные сценарии управления диалогом»).

## Следующее действие

S4-08 завершена — Sprint 4 (S4-01…S4-08) полностью завершён. Полный
аудит `bootstrap/container.py` (DI-сборка `FileTemplateRepository`/
`TokenBudgetPolicy`/`DeterministicPromptBuilder`, бюджет из
`Settings.prompt.token_budget`) не выявил ни одного дефекта — вся
сборка уже была корректно подключена задачей S4-07; в отличие от S2-11/
S3-09 (каждая нашла и точечно исправила один-два реальных
интеграционных дефекта), S4-08 не нашла новых дефектов, требующих
исправления — честный результат аудита, не подогнанный под ожидание
«обязательно что-то найти». Эмпирически подтверждено: собранный
системный промпт реально содержит секцию активного профиля и не пуст
(`tests/e2e/test_prompt_engine_scenario.py`, дополняет уже существующую
проверку видимой разницы между двумя профилями в
`tests/e2e/test_profile_scenario.py`); искусственно длинный диалог (25
сообщений) с заведомо малым бюджетом `TokenBudgetPolicy` (1500 символов)
реально обрезается на полном вертикальном срезе (Telegram-хендлер →
`ProcessUserMessage` → `PromptBuilder` → `LLMProvider`), последнее
сообщение (текущий запрос) сохранено, ответ пользователю приходит
нормально; реальный Docker-образ собран и запущен, `/health` отвечает
`200`, `alembic upgrade head` → `downgrade -1` → `upgrade head` внутри
контейнера проходит без ошибок (сид-каталог восстанавливается: 4
профиля, 1 `is_default`), `FileTemplateRepository()` внутри контейнера
реально находит и загружает все 6 сид-шаблонов (проверка
`package-data`-фикса из S4-04 на настоящем образе, не только на
локальном wheel), `build_container()` внутри контейнера собирает
`ProcessUserMessage` с бюджетом `12000` из `.env`/`Settings`, не
хардкод. 496 тестов, ruff/ruff format/mypy проходят. `README.md`
обновлён под фактическое состояние Sprint 4 (диаграмма сценария,
дерево каталогов, переменные окружения, тесты, абзац про мёртвый
v2.0-скелет). Следующий шаг — Этап 7, долговременная память (§33), не
начат.

S5-08 завершена — Sprint 5 (S5-01…S5-08) полностью завершён. Полный
аудит `bootstrap/container.py` (DI-сборка `SQLAlchemyMemoryRepository`
через `repositories_factory`, `MemorySettings.max_relevant_records` в
`ProcessUserMessage`, три use case'а памяти —
`CreateMemoryRecordUseCase`/`ListMemoryRecordsUseCase`/
`DeleteMemoryRecordUseCase`) не выявил ни одного дефекта — вся сборка
уже была корректно подключена задачами S5-03…S5-07; как и S4-08 (и в
отличие от S2-11/S3-09, каждая из которых нашла и точечно исправила
один-два реальных интеграционных дефекта), S5-08 не нашла новых
дефектов, требующих исправления. Эмпирически подтверждено:
`tests/e2e/test_memory_prompt_scenario.py` доказывает «Сценарий 4» §18.4
«Плана реализации.md» буквально — `/remember` → `/new` → обычное
сообщение → собранный `system_prompt` реально содержит сохранённый
факт (эквивалент прямой проверки `PromptBuildResult.system_prompt`,
`LLMRequest.system_prompt=build_result.system_prompt` без преобразований,
ADR-4.1); факт пользователя A никогда не появляется в промпте
пользователя B; `/clear`/`/new` не удаляют `memory_records` (факт
по-прежнему в `/memory` после очистки истории/начала нового диалога);
редакция чувствительных записей в логах подтверждена не только на
fake-репозитории (S5-05), но и поверх РЕАЛЬНОГО
`SQLAlchemyMemoryRepository` — создание/удаление записи с
`is_sensitive=True` не публикует `record.text` в JSON-вывод
`shared/logging.py`. Реальный Docker-образ собран и запущен, `/health`
отвечает `200`, `alembic upgrade head` → `downgrade -1` → `upgrade head`
внутри контейнера проходит без ошибок; схема `memory_records`
(`CHECK`-ограничения на `category`/`source`/`status`/`confidence`, FK
`user_id → users.id`, индекс `(user_id, status)`) подтверждена прямым
запросом к `sqlite_master` внутри контейнера, не только по исходнику
миграции; `Settings().memory.max_relevant_records == 5` (значение по
умолчанию, не заданное явно в `.env`) и полный состав полей
`ApplicationContainer` (включая три use case'а памяти) подтверждены
реальным импортом внутри собранного образа. 565 тестов, ruff/ruff
format/mypy проходят. `README.md` обновлён под фактическое состояние
Sprint 5 (диаграмма сценария включает память в цепочку
`ProcessUserMessage`, дерево каталогов — `domain/memory`/
`application/memory`/новые файлы `infrastructure/persistence/`/
`presentation/telegram/handlers/memory.py`, раздел «База данных и
миграции» — четвёртая ревизия без сид-данных, таблица переменных
окружения — `MemorySettings`, раздел «Тесты» —
`test_memory_scenario.py`/`test_memory_prompt_scenario.py`, абзац про
мёртвый v2.0-скелет — про удаление узла памяти в S5-01); `.env.example`
дополнен `MemorySettings`. Следующий шаг — Этап 8, база знаний и RAG
(§33), не начат.

(Между этой записью и следующей нет отдельной записи «S6-11 завершена»
— тот же пробел в процессе, что и в §32/«Известные расхождения» выше:
Sprint 6, Этап 8, реально завершён по коммитам `feature/sprint-6`, этот
файл просто не был обновлён в момент его завершения.)

S7-08 завершена — Sprint 7 (S7-01…S7-08) полностью завершён. Полный
аудит `bootstrap/container.py` (DI-сборка `ConfigModelCatalogRepository`
из `settings.model_catalog.catalog_path`, внедрение `model_catalog` в
`ProcessUserMessage`, сборка `list_available_models`/`get_selected_model`/
`select_model` поверх той же `repositories_factory` и того же
`model_catalog`) не выявил ни одного дефекта — вся сборка уже была
корректно подключена задачами S7-06/S7-07; как и S4-08/S5-08 (и в
отличие от S2-11/S3-09, каждая из которых нашла и точечно исправила
один-два реальных интеграционных дефекта), S7-08 не нашла новых
интеграционных дефектов в коде — единственная правка этой задачи была
запланированной точечной правкой докстринга (`prompt_builder.py`,
«Этап 10» → «Этап 9»), не найденным дефектом. Эмпирически подтверждено:
`tests/e2e/test_model_selection_scenario.py` доказывает, что выбор
модели через `/model` реально меняет `LLMRequest.model_id`/
`temperature`/`max_tokens` (сверено со значениями `default_generation_
settings` боевой модели каталога, отличающимися от `Settings.llm`,
переданных в конструктор — совпадение результата с каталожными
значениями исключает случайное совпадение); откат при недоступности
подтверждён и по значению `model_id`, и по факту записи в лог
(`model_selection_fallback`, `level=warning`, поля `requested_model_id`/
`fallback_model_id`/`user_id`) через `capsys`+JSON-парсинг строки, не
только «ответ пришёл»; выбор одного пользователя не виден другому;
полный цикл `/model` → клавиатура (с пометкой «(недоступна)» на боевой
`anthropic/claude-3-haiku`) → выбор через реальный `CallbackQueryHandler`
→ обновлённая клавиатура; попытка выбрать `UNAVAILABLE`-модель
отклонена и видна пользователю (`show_alert=True`), список не
редактируется. Реальный Docker-образ собран и запущен: `/health`
отвечает `200`; `catalog.json` подтверждён установленным пакетом
(`pip install .`, прямой импорт `ConfigModelCatalogRepository()` внутри
образа — 6 моделей, путь внутри `site-packages`, не подхватывался бы
без правки `pyproject.toml::package-data`, тот же класс проверки, что
шаблоны Prompt Engine в S4-04 и `scripts/` в S6-11); `alembic upgrade
head → downgrade -1 → upgrade head` внутри контейнера проходит дважды —
на чистой временной БД И на реальном персистентном volume, оставшемся
от предыдущих сессий тестирования Sprint 1-6 (миграция с `82d9884e32a2`
на `ed5701d2f683`, таблица `user_active_models` подтверждена прямым
запросом к `sqlite_master`); `docker compose up -d` (все три сервиса —
api/telegram-bot/qdrant) — оба процесса приложения стартуют и логируют
штатно, без единой ошибки/traceback. 741 тест, ruff/ruff format/mypy
проходят. `README.md` обновлён под фактическое состояние Sprint 7.
Следующий шаг — Этап 10, административные функции (§33), не начат.

S8-11 завершена — Sprint 8 (S8-01…S8-11) полностью завершён. Полный
аудит `bootstrap/application.py`/`bootstrap/container.py`/`bootstrap/
knowledge_container.py` не выявил новых дефектов сверх уже найденных и
исправленных по ходу самих задач (S8-01 — dangling-импорт мёртвого
`AdminAuthPort`/`AuthenticateAdminUseCase` в живом `composition/
container.py`, транзитивно ломавший тестируемый `composition/
bootstrap.py`; S8-05/S8-08/S8-09 — необходимость локального (не
module-level) импорта трёх новых роутеров внутри `create_application()`,
иначе цикл импорта `bootstrap.application` ↔
`presentation.api.routes.*`/`presentation.api.dependencies.documents`,
поскольку их зависимости импортируют accessor-функции обратно из
`bootstrap.application`); DI-сборка корректна — `ApplicationContainer`
содержит ровно 4 новых профильных поля (`create_profile`/
`update_profile`/`deactivate_profile`/`list_all_profiles`) плюс
`check_external_services_health` (ADR-8.4 checklist подтверждён
буквально), `bootstrap/knowledge_container.py` — три новых билдера
(`build_list_documents_use_case`/`build_get_document_use_case`/
`build_reindex_document_use_case`), ровно одна
`ConversationRepositoriesFactory` во всём приложении (`grep` находит
единственный вызов `build_conversation_repositories_factory`, в
`bootstrap/container.py`).

Эмпирически подтверждено (`tests/e2e/test_admin_scenario.py`, новый):
один continuous-прогон через реальный `create_application()` lifespan —
401 без ключа/с неверным ключом на всех трёх admin-роутерах; полный
жизненный цикл документа (`upload → list → get → reindex → delete →
404`, `reindex` сохраняет `document_id`); полный жизненный цикл профиля
(`create → patch (частичный) → archive → list`, попытка архивировать
`is_default=True` → `409 PROFILE_ARCHIVE_DEFAULT_FORBIDDEN`, профиль
остаётся `ACTIVE`); `GET /admin/health` — оба крайних сценария (все три
сервиса здоровы/все три недоступны) в одном и том же прогоне; публичный
`GET /health` не задет присутствием admin-роутеров. `git diff --stat
feature/sprint-7..HEAD -- domain/prompt application/prompt
infrastructure/prompts process_user_message.py presentation/telegram` —
пусто (диалоговый путь и Telegram-хендлеры не тронуты ни одним байтом
за весь спринт).

Docker-верификация выполнена реально, не сфабрикована (Docker Desktop
запущен и проверен в рамках этой сессии): `docker compose build` —
успешно (оба образа, `api`/`telegram-bot`, из одного `Dockerfile`,
включая новую рантайм-зависимость `python-multipart`); `docker compose
up -d` — все три сервиса (`api`/`telegram-bot`/`qdrant`) стартуют
штатно, `api` отчитывается `healthy` через встроенный Docker
healthcheck; `GET /health` (без ключа) → `200`, контракт не изменился;
`GET /admin/health` без ключа/с неверным ключом → `401` оба раза; `GET
/admin/health` С РЕАЛЬНЫМ `ADMIN_API_KEY` (значение из локального
`.env`, не в git) И РЕАЛЬНЫМИ `OPENROUTER_API_KEY`/`OPENAI_API_KEY` →
`200`, все три сервиса `healthy: true`, включая Qdrant, увиденный по
имени сервиса Docker Compose `qdrant` (не `localhost`) — прямое
эмпирическое подтверждение сетевого решения `docker-compose.yml::
QDRANT_HOST=qdrant`; `alembic current`/`alembic history` внутри
контейнера подтверждают ровно 6 миграций, без единой новой ревизии для
`profiles`/`knowledge_documents` (список ревизий идентичен состоянию до
Sprint 8); `alembic upgrade head → downgrade -1 → upgrade head` внутри
контейнера — чисто, без ошибок; прямой запрос к `sqlite_master` внутри
контейнера после цикла подтверждает все 8 таблиц на месте (`users`,
`conversations`, `messages`, `profiles`, `user_active_profiles`,
`memory_records`, `knowledge_documents`, `user_active_models`).
`scripts/check_services.py`/`scripts/index_document.py list` отработали
штатно внутри контейнера (реальные HTTP-вызовы к Qdrant/OpenRouter/
OpenAI, не фейки). Дополнительно, сверх формальных требований S8-11:
полный документный цикл выполнен внутри контейнера СКВОЗЬ ОБА интерфейса
одновременно, доказывая, что CLI и REST реально используют одну и ту же
композицию (не два похожих, но раздельных пути) — `python
scripts/index_document.py index` (CLI, реальный OpenAI embeddings-вызов,
реальный Qdrant upsert, `status=indexed chunk_count=1`) → документ
немедленно виден через `GET /admin/documents/{id}` (REST) → `POST
/admin/documents/{id}/reindex` (REST) возвращает тот же `document_id` →
`python scripts/index_document.py delete` (CLI) → `GET
/admin/documents/{id}` (REST) → `404`; отдельно — попытка архивировать
РЕАЛЬНЫЙ сид-профиль `is_default=True» («Деловой», из сид-миграции
S3-04, не тестовые данные) через REST против настоящего контейнера и
настоящей персистентной БД → `409 PROFILE_ARCHIVE_DEFAULT_FORBIDDEN`,
профиль не изменён.

842 теста проходят (было 741 на конец Sprint 7), Ruff, Ruff format, MyPy
проходят без ошибок. `README.md` обновлён под фактическое состояние
Sprint 8 (переменная `ADMIN_API_KEY`, раздел «Admin API» с перечнем всех
11 admin-эндпоинтов, обновлённое дерево каталогов, обновлённый раздел
«Тесты»). Следующий шаг — Этап 11 (полноценный просмотр логов/метрик,
`AccessDeniedError`/`ConfigurationError`/`KnowledgeSearchError`, сквозной
`correlation_id`), не начат.
