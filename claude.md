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
инструкции (S3-01…S3-09), в разработке.**

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

## Спринт 8

* административные функции;
* аудит;
* метрики;
* production-развёртывание;
* приёмочные тесты.
* явный глобальный `exception_handler` для FastAPI (`bootstrap/application.py`) —
  до сих пор непокрытая граница интерфейса опиралась на дефолтное
  поведение Starlette (`debug=False` → общий `500` без traceback), т.к.
  единственный эндпоинт был `/health` и не мог бросить содержательное
  исключение; с первым эндпоинтом, вызывающим use case/бизнес-логику,
  нужна та же явная обработка `DekoderError`/неожиданных исключений, что
  уже есть в Telegram-обработчике (`presentation/telegram/handlers/messages.py`)
  — безопасное сообщение пользователю, без stack trace и внутренних деталей.

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
интеграция и E2E-проверка) — Спринт 2 полностью завершён.

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

Ничего — Sprint 2 полностью завершён (S2-01…S2-11). Следующий шаг —
Sprint 3 (профили, §33).

## Не реализовано

* профили, Prompt Engine, память, RAG, каталог моделей, административные
  функции — по плану, следующие спринты (§33).

## Известные расхождения

**В репозитории одновременно существуют два несовместимых дерева
исходного кода.** До прочтения этого файла (в той же сессии) была
выполнена большая, отдельная миграция по `docs/versions/*_v2.0.md`:
`composition/`, `interfaces/`, `domain/`/`application/`-модули `ai_core`,
`admin`, `profile`, `memory`, `knowledge_base`, `rag`, `model_catalog`,
`logging`, LLM-адаптеры под `infrastructure/model_gateway/` — почти 200
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

S2-11 завершена — Sprint 2 (S2-01…S2-11) полностью завершён и готов к
финальной приёмке. Аудит composition root/DI/транзакций/конфигурации/
миграций подтвердил, что все компоненты S2-01…S2-10 уже были корректно
собраны и подключены; найдены и точечно исправлены три реальных
интеграционных дефекта (недетерминированный порядок `MessageRepository.
history()` при совпадении `created_at` — фикс в `ProcessUserMessage.
_build_message`; отсутствие прав на `/app/data` для непривилегированного
пользователя в `Dockerfile`; отсутствие persistent volume в
`docker-compose.yml` — оба Docker-дефекта не позволяли постоянному
хранилищу Sprint 2 реально пережить перезапуск контейнера, хотя ни один
существующий тест их не ловил, т.к. тесты используют временную SQLite
напрямую, не Docker) — подробности см. выше, запись S2-11. Новая
бизнес-функциональность не добавлялась (только исправления/тесты/
документация). Следующий шаг — Sprint 3 (пользовательские профили,
§33), не начат.
