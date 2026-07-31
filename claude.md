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

**Спринт 2: постоянное хранилище данных, диалоги, история — начат.**

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
* [ ] S2-05 и далее — `MessageRepository`, расширение
  `ProcessUserMessage` историей, `/new`, `/clear` — не начаты.

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
(`UserRepository`) и S2-04 (`ConversationRepository`) — Спринт 2.

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

## В разработке

Ничего в рамках S2-04 — задача закрыта полностью (порт, SQLAlchemy-
реализация, bootstrap-фабрика, тесты, claude.md). Следующий шаг — S2-05:
`MessageRepository` (§33).

## Не реализовано

* `MessageRepository`, расширение `ProcessUserMessage` историей диалога
  (включая подключение уже готовых `UserRepository`/
  `ConversationRepository`), команды `/new`/`/clear` — следующие задачи
  Sprint 2 (S2-05 и далее, §33);
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

## Следующее действие

Начать S2-05 (§33, внешняя спецификация `backlog_2.md`, §8):
`MessageRepository` (интерфейс + SQLAlchemy-реализация поверх
`MessageORM`/mapper'ов S2-02 — сохранение сообщения, получение истории
диалога в хронологическом порядке `created_at ASC, id ASC`, удаление всех
сообщений диалога для будущей команды `/clear`) — по отдельному запросу
пользователя, не автоматически.
