# Декодер

Персональный AI-ассистент «Декодер». Целевая архитектура и полный
состав возможностей (профили автора, Content Skills, административная
панель) описаны в [`CLAUDE.md`](claude.md) и в `docs/versions/` — это
проектные документы, а не описание того, что уже запускается.

**Что реально работает сейчас** — Sprint 1 (Walking Skeleton), Sprint 2
(постоянное хранилище, диалоги, история), Sprint 3 (пользовательские
профили), Sprint 4 (Prompt Engine — централизованная сборка промпта),
Sprint 5 (долговременная память), Sprint 6 (база знаний и RAG через
Qdrant), Sprint 7 (выбор AI-модели пользователем) и Sprint 8
(административные функции — защищённый REST API для документов базы
знаний и профилей, реальные health-check внешних сервисов, CLI-паритет)
полностью завершены:

```text
Telegram → ProcessUserMessage → (модель + профиль + память + история + RAG) → PromptContext → PromptBuilder → PromptBuildResult
                 │                                                                                                    │
                 ├── User/Conversation/Message/выбор модели сохраняются в SQLite                                     │
                 └──────────────────────────────────────────────────────────────── LLMRequest.model_id → LLMProvider → OpenAiCompatibleLLMAdapter → ответ

Telegram /new      → StartNewConversation → закрывает текущий диалог, создаёт новый (память не трогает)
Telegram /clear    → ClearConversation    → удаляет историю, диалог остаётся активным (память не трогает)
Telegram /profile  → ListProfiles/GetActiveProfile/SelectProfile → выбор профиля через inline-клавиатуру
Telegram /remember → CreateMemoryRecordUseCase → сохраняет факт сразу подтверждённым (status=CONFIRMED)
Telegram /memory   → ListMemoryRecordsUseCase → список подтверждённых фактов с inline-удалением (🗑)
Telegram /model    → ListAvailableModels/GetSelectedModel/SelectModel → выбор AI-модели через inline-клавиатуру
```

Пользователь пишет боту в Telegram → сообщение уходит в use case
`ProcessUserMessage` → пользователь и его активный диалог находятся или
создаются в SQLite, читается его активный профиль (`ProfileRepository`),
до `MemorySettings.max_relevant_records` (по умолчанию 5) подтверждённых
записей памяти (`MemoryRepository.find_relevant` — только `CONFIRMED`, не
истёкшие, отсортированные по значимости и свежести, Sprint 5) и
разрешается активная AI-модель (Sprint 7: явный override →
персональный выбор пользователя, `ModelSelectionRepository.get_selected` →
`LLM_PROVIDER_DEFAULT_MODEL`; недоступная/отсутствующая в каталоге модель
— тихий логируемый откат на умолчание, без диалога с пользователем),
сообщение пользователя сохраняется → история диалога читается из базы →
выполняется семантический поиск по базе знаний (Sprint 6: эмбеддинг
запроса → поиск в Qdrant → найденные фрагменты с указанием источника;
сбой поиска не обрушивает ответ — просто нет RAG-контекста в этом
ответе) → `ProcessUserMessage` собирает `PromptContext` (профиль +
подтверждённая память + история + фрагменты базы знаний) и передаёт его
`PromptBuilder` (Prompt Engine, Sprint 4) — тот детерминированно собирает
системную инструкцию из 8 фиксированных секций (базовая инструкция,
правила безопасности, параметры активного профиля — используются ВСЕ
описательные поля профиля, не только `system_instruction`, —
подтверждённая память, найденные источники базы знаний, история диалога,
текущий запрос, требования к формату ответа), исключая пустые секции и
ограничивая суммарный объём эвристическим `TokenBudgetPolicy` (обрезает
старую историю первой, если она есть; текущий запрос и системные секции
неприкосновенны) → адаптер `OpenAiCompatibleLLMAdapter` вызывается с
разрешённой моделью и её `temperature`/`max_tokens` из каталога (если
модель в нём есть — иначе `LLM_TEMPERATURE`/`LLM_MAX_TOKENS`) → ответ
модели сохраняется как сообщение ассистента и возвращается пользователю
в Telegram; версии использованных шаблонов промпта доступны в
`ProcessUserMessageResult.prompt_template_versions`.
Команда `/new` закрывает текущий диалог и начинает новый (старая история
не удаляется, просто перестаёт быть активной; подтверждённая память не
удаляется — память не равна истории сообщений, §13.5 «Плана
реализации.md»); `/clear` удаляет сообщения текущего диалога, не закрывая
и не пересоздавая сам диалог и не трогая память; `/profile` показывает
каталог из 4 предустановленных профилей с отметкой текущего активного и
позволяет переключиться через inline-кнопку — переключение влияет только
на будущие сообщения, не переписывает уже сохранённую историю, и не
влияет на других пользователей; `/remember <текст>` сохраняет факт сразу
подтверждённым, без двухшагового сценария (ADR-5.9); `/memory` показывает
только подтверждённые факты с кнопкой 🗑 на каждой записи — удаление
только через inline-кнопку, команды `/forget` нет (ADR-5.10); один
пользователь никогда не видит и не может удалить факты другого
(`user_id`-изоляция на уровне `MemoryRepository`, не только Telegram-слоя);
`/model` показывает статичный каталог AI-моделей (`infrastructure/
model_catalog/catalog.json`, 6 иллюстративных моделей из 4 семейств
поставщиков, см. раздел «Каталог AI-моделей» ниже) с отметкой текущей выбранной и явной пометкой «(недоступна)»
у моделей, помеченных в каталоге неактивными — выбор такой модели
отклоняется на уровне use case, не только UI; переключение влияет только
на будущие сообщения и не затрагивает других пользователей.
Реальных прямых (не через настроенный `LLM_PROVIDER_BASE_URL`) адаптеров провайдеров и
интеллектуальной авто-маршрутизации между моделями ещё нет — они
добавляются по следующим спринтам/этапам (`claude.md`, §33).
Автоматическое извлечение фактов AI из диалога не реализовано и
не планируется в MVP (§13.2 «Плана реализации.md») — память растёт
только через явную команду `/remember`.

Sprint 8 добавляет защищённый административный REST API
(`presentation/api/`, все эндпоинты — под заголовком
`X-Admin-Api-Key`) поверх той же архитектуры: CRUD документов базы
знаний (список/детали/загрузка+индексация/удаление/переиндексация),
CRUD профилей (список/создание/редактирование/архивация) и реальные
проверки доступности Qdrant/LLM-провайдера/OpenAI (`GET /admin/health`) —
без единого изменения в `ProcessUserMessage`, Prompt Engine или
Telegram-командах. Подробности — раздел «Admin API» ниже.

## Архитектура

Modular Monolith, Clean Architecture / Ports and Adapters. Направление
зависимостей:

```text
presentation → application → domain
infrastructure → (implements) → application ports
bootstrap → собирает presentation + application + infrastructure
```

Реально используемые каталоги для этого среза:

```text
src/dekoder/
├── domain/
│   ├── conversation/                # MessageText/ModelId/ProviderId, MessageRole, Message, Conversation (Aggregate Root)
│   ├── user/                        # User
│   ├── profile/                     # UserProfile, ProfileStatus (Sprint 3, S3-02)
│   ├── prompt/                      # PromptTemplate/PromptTemplateStatus, PromptSection/PromptContext/
│   │                                 #   PromptBuildResult, TokenBudgetPolicy (Sprint 4, S4-02)
│   ├── memory/                      # MemoryRecord, MemoryCategory/MemorySource/MemoryStatus/MemoryConfidence (Sprint 5, S5-02)
│   ├── knowledge/                   # KnowledgeDocument, SearchResult/SourceReference (Sprint 6, S6-03)
│   └── model_catalog/               # AIModel, ModelSelection, AIProvider/ModelCapability/ModelAvailability/
│                                     #   ModelPriceTier, GenerationSettings (Sprint 7, S7-02/S7-04)
├── application/
│   ├── conversation/                # DTO, LLMProvider/ConversationRepository/MessageRepository/ConversationRepositories (порты),
│   │                                 #   ProcessUserMessage, StartNewConversation, ClearConversation
│   ├── user/                        # UserRepository (порт)
│   ├── profile/                     # ProfileRepository (порт), DTO, ListProfiles/GetActiveProfile/SelectProfile (S3-05/S3-06)
│   ├── prompt/                      # PromptBuilder/PromptTemplateRepository (порты, S4-03);
│   │                                 #   services/prompt_builder.py::DeterministicPromptBuilder (S4-05),
│   │                                 #   services/token_budget.py::estimate_size (S4-06)
│   ├── memory/                      # MemoryRepository (порт, S5-03), DTO, use_cases/ — CreateMemoryRecord/
│   │                                 #   ConfirmMemoryRecord/RejectMemoryRecord/ListMemoryRecords/DeleteMemoryRecord (S5-05)
│   ├── knowledge/                   # KnowledgeDocumentRepository/KnowledgeSearchService (порты, S6-03/S6-04),
│   │                                 #   services/semantic_search_service.py::SemanticSearchService (S6-07),
│   │                                 #   use_cases/{index_document,delete_document}.py (S6-06)
│   └── model_catalog/               # ModelCatalogRepository/ModelSelectionRepository (порты, S7-03/S7-04), DTO,
│                                     #   use_cases/{list_models,get_selected_model,select_model}.py (S7-05)
├── infrastructure/
│   ├── llm/                         # OpenAiCompatibleLLMAdapter (дженерик, Sprint 11, ADR-11.1)
│   ├── persistence/                 # base.py/engine.py/session.py (SQLAlchemy async, S2-01) +
│   │                                 #   user_orm.py/conversation_orm.py/message_orm.py + mappers.py (S2-02) +
│   │                                 #   user_repository.py/conversation_repository.py/message_repository.py (S2-03..S2-05) +
│   │                                 #   profile_orm.py/user_active_profile_orm.py/profile_repository.py (Sprint 3, S3-03/S3-05) +
│   │                                 #   memory_record_orm.py/memory_repository.py::SQLAlchemyMemoryRepository (Sprint 5, S5-04) +
│   │                                 #   knowledge_document_orm.py/knowledge_document_repository.py (Sprint 6, S6-04) +
│   │                                 #   user_active_model_orm.py/sqlalchemy_model_selection_repository.py (Sprint 7, S7-04)
│   ├── prompts/                     # file_template_repository.py::FileTemplateRepository +
│   │                                 #   templates/{manifest.json, *.txt} — 6 сид-шаблонов (Sprint 4, S4-04)
│   ├── documents/                   # parsers/{txt,markdown,docx,pdf}_parser.py, chunking/structural_chunker.py (Sprint 6, S6-05)
│   ├── embeddings/                  # openai_embedding_provider.py::OpenAiEmbeddingProvider (Sprint 6, S6-05)
│   ├── qdrant/                      # client.py, vector_repository.py::QdrantVectorRepository (Sprint 6, S6-02/S6-05)
│   ├── filesystem/                  # local_document_storage.py — хранилище исходных файлов документов (Sprint 6, S6-05)
│   └── model_catalog/               # catalog.json (сид, 6 иллюстративных моделей/4 поставщика) +
│                                     #   config_repository.py::ConfigModelCatalogRepository (Sprint 7, S7-03)
├── presentation/telegram/           # /start, /new, /clear, /profile, /remember, /memory (S5-07), /model (S7-07),
│                                     #   обработчик текстовых сообщений, mapper.py, bot.py
├── bootstrap/                       # container.py, application.py, database.py, repositories.py — единственное место сборки
└── shared/                          # config.py, logging.py, errors.py

alembic/                             # users/conversations/messages (S2-02) + profiles/user_active_profiles (S3-03) +
                                      #   сид-каталог из 4 профилей (S3-04) + memory_records (S5-04) +
                                      #   knowledge_documents (Sprint 6, S6-04) + user_active_models
                                      #   (Sprint 7, S7-04, ADR-7.5) — все схемные миграции после сид-каталога
                                      #   профилей без сид-данных; Sprint 4 не добавляет миграций (шаблоны
                                      #   промпта — файловое хранилище, не БД, ADR-4.2); каталог моделей —
                                      #   тоже файловое хранилище (catalog.json), не БД (ADR-7.4)

scripts/index_document.py            # CLI-скрипт индексации/удаления документов базы знаний (Sprint 6, S6-09)
```

> В репозитории также существует более крупное, отдельное от этого
> среза дерево-заглушка — `composition/`, `interfaces/`, а также модули
> `ai_core`, `admin`, `session`, `skills`, `knowledge_base`, `rag` под
> `domain/`/`application/`. Это результат более ранней миграции по
> документам `docs/versions/*_v2.0.md`, построенной по другой архитектуре
> (`interfaces/`+`composition/` вместо `presentation/`+`bootstrap/`).
> Реально запускаемое приложение (`main.py`, `telegram_main.py`) его не
> использует — почти весь код там оканчивается `raise
> NotImplementedError`. Реконсиляция оставшихся модулей — сознательно
> отложенное решение, подробности в `claude.md`, §36. Мёртвый скелет
> `domain/profile/`/`application/profile/*` из этого дерева был удалён в
> Sprint 3 (задача S3-01) — он конфликтовал по имени/форме с реальным
> `UserProfile`, который этот срез теперь использует. Мёртвый
> `infrastructure/logging/`/`application/logging/*`/`domain/logging/*`
> (v2.0-логгер, не используемый реальными composition root'ами — они
> используют `shared/logging.py`) и мёртвый `application/prompt_engine/`/
> `application/ai_core/internal_services/prompt_assembler.py` (второй,
> нерабочий «построитель промпта») были удалены в Sprint 4 (задача
> S4-01) — оба создавали прямой риск путаницы именно в момент, когда
> строился настоящий Prompt Engine (`domain/prompt/`, `application/
> prompt/`, `infrastructure/prompts/`). Мёртвый узел памяти
> (`application/memory/*` со старой формой `DialogueEntry`/`MemoryFact`/
> `MemoryFactDraft`, `domain/memory/*`, `infrastructure/persistence/
> sqlite_memory_repository.py`, `application/ai_core/internal_services/
> memory_collector.py`) был удалён в Sprint 5 (задача S5-01), мёртвый
> узел базы знаний/RAG (`domain/knowledge_base/`, `application/
> knowledge_base/`, `domain/rag/`, `application/rag/`,
> `infrastructure/vector_storage/`, `interfaces/admin_http/`) — в
> Sprint 6 (задача S6-01), а мёртвый узел каталога моделей
> (`domain/model_catalog/model_definition.py` — плоский `ModelDefinition`,
> `application/model_catalog/*` со старой формой `list_compatible(...)`,
> `application/model_gateway/`, `infrastructure/model_gateway/`,
> `infrastructure/persistence/sqlite_model_catalog_repository.py`) — в
> Sprint 7 (задача S7-01, ADR-7.1) — той же логикой: прямой риск
> путаницы именно в момент, когда строилась настоящая версия каждой
> подсистемы (реальная память — `domain/memory/`; реальная база знаний —
> `domain/knowledge/`; реальный каталог моделей — `domain/model_catalog/`
> с формой `AIModel`/`AIProvider`/`ModelCapability`/`ModelAvailability`/
> `GenerationSettings`, использующий живой `ModelId` из
> `domain/conversation/value_objects.py`, а не мёртвый из
> `shared/domain/identifiers.py`). Остальной v2.0-скелет (`admin`, `rag`,
> `session`, `skills`, `interfaces/`, `composition/`) по-прежнему не
> тронут — признан нежизнеспособным, но его зачистка вынесена в
> отдельную будущую задачу (ADR-4.10/5.1/6.x/7.1).

## Технологический стек

Python 3.11+, FastAPI, uvicorn, python-telegram-bot, httpx,
pydantic / pydantic-settings, structlog. С Sprint 2 подключены и
полностью используются SQLAlchemy 2.x (async, `AsyncEngine`/`AsyncSession`),
`aiosqlite` и Alembic — постоянное хранилище `users`/`conversations`/
`messages`/`profiles`/`user_active_profiles`/`memory_records`/
`knowledge_documents`/`user_active_models` (ORM-модели, репозитории,
шесть миграций схемы + одна data migration в `alembic/versions/`), с
`PRAGMA foreign_keys=ON` для каждого SQLite-соединения
(`infrastructure/persistence/engine.py`).
Prompt Engine (Sprint 4) не добавляет ни одной новой зависимости —
подстановка переменных в шаблоны промпта использует только стандартную
библиотеку (`string.Template`), не Jinja2 и не другой шаблонизатор;
шаблоны хранятся в текстовых файлах за портом, не в БД (ADR-4.2).
С Sprint 6 подключены `qdrant-client` (векторное хранилище для RAG,
отдельный сервис `qdrant` в `docker-compose.yml`), `python-docx`/`pypdf`
(парсинг документов `.docx`/`.pdf` базы знаний) — эмбеддинги считаются
через настроенный `EMBEDDING_PROVIDER_BASE_URL` (по умолчанию — прямой
OpenAI, `EMBEDDING_PROVIDER_API_KEY`, отдельно от `LLM_PROVIDER_*` —
выбранный LLM-агрегатор не гарантированно отдаёт embeddings API), а не
через настроенный LLM-провайдер. С Sprint 12 (ADR-12.1) провайдер
эмбеддингов параметризован — можно направить на OpenAI-совместимый
агрегатор (например RouterAI), не только на прямой OpenAI.
Каталог AI-моделей (Sprint 7) не добавляет ни одной новой зависимости —
статичный JSON-файл (`infrastructure/model_catalog/catalog.json`),
парсится через уже используемый `pydantic` (ADR-7.4); с Sprint 11
(ADR-11.1) LLM-провайдер — дженерик OpenAI-Chat-Completions-совместимый
адаптер, настраиваемый через `LLM_PROVIDER_*` (не зафиксирован на одном
вендоре) — выбор модели меняет только значение `LLMRequest.model_id`,
отправляемое тому же `OpenAiCompatibleLLMAdapter`, не добавляет второй
HTTP-клиент/адаптер.
Sprint 8 (admin REST) добавляет ровно одну новую рантайм-зависимость —
`python-multipart` (обязательна для FastAPI `Form`/`UploadFile` в `POST
/admin/documents`, без неё запрос падает `500` на рантайме); авторизация
— штатный `fastapi.security.APIKeyHeader`, без сторонних библиотек;
health-check переиспользует уже подключённые `httpx`/`qdrant-client`, не
добавляет собственных HTTP-клиентов.

## Быстрый старт (локальная разработка)

Предварительно нужны:

- Python 3.11+;
- [uv](https://docs.astral.sh/uv/);
- токен Telegram-бота (создать через [@BotFather](https://t.me/BotFather));
- API-ключ любого OpenAI-Chat-Completions-совместимого LLM-агрегатора
  (например, [OpenRouter](https://openrouter.ai/keys) — не единственный
  вариант, см. `LLM_PROVIDER_*` ниже, ADR-11.1).

```powershell
git clone <URL этого репозитория>
cd Decoder

uv venv
uv pip install -e ".[dev]"

cp .env.example .env.local   # заполнить TELEGRAM_BOT_TOKEN, LLM_PROVIDER_API_KEY/BASE_URL/DEFAULT_MODEL
uv run pre-commit install

uv run pytest   # должно пройти без реальных секретов — внешние вызовы замоканы
```

Запуск двух процессов (в отдельных терминалах):

```powershell
# Процесс 1 — ASGI API (/health и т.д.)
uv run uvicorn dekoder.main:app --reload

# Процесс 2 — Telegram bot (long polling)
uv run python -m dekoder.telegram_main
```

**Перед первым запуском примените миграции** (создают `./data/app.db` со
всей текущей схемой — см. раздел «База данных и миграции» ниже):

```powershell
uv run alembic upgrade head
```

После этого можно написать боту `/start`, затем любое текстовое
сообщение — оно уйдёт настроенному через `LLM_PROVIDER_BASE_URL`
провайдеру, а сам диалог (пользователь, диалог,
оба сообщения) сохранится в SQLite. Дальнейшие сообщения того же
пользователя продолжают тот же диалог — LLM получает всю историю.

Дополнительные команды:

- `/new` — закрывает текущий диалог и начинает новый с чистой историей
  (старый диалог и его сообщения никуда не пропадают, просто перестают
  быть активными); если бот ещё не видел этого пользователя — отвечает
  нейтральным сообщением, ничего не создавая;
- `/clear` — удаляет всю историю текущего активного диалога, сам диалог
  остаётся тем же самым (тот же `conversation_id`) — следующее сообщение
  продолжает его же, с чистой историей;
- `/profile` — показывает каталог из 4 предустановленных профилей
  («Экспертный», «Дружелюбный», «Деловой» — профиль по умолчанию,
  «Креативный») с inline-клавиатурой, текущий активный отмечен в тексте
  кнопки; выбор профиля меняет системную инструкцию, которую видит LLM
  при каждом следующем ответе — переключение не затрагивает уже
  отправленные сообщения и не влияет на других пользователей;
- `/remember <текст>`/`/memory` — сохраняет и показывает долговременные
  факты о пользователе (Sprint 5), учитываются в ответах через секцию 4
  промпта;
- документы базы знаний индексируются офлайн через `python -m
  scripts.index_document` (Sprint 6, не Telegram-команда) — после
  индексации релевантные фрагменты автоматически подмешиваются в ответ
  через RAG, без явного действия пользователя в чате;
- `/model` — показывает статичный каталог AI-моделей с inline-клавиатурой,
  текущая выбранная отмечена в тексте кнопки, недоступные — пометкой
  «(недоступна)» (выбрать такую модель нельзя — use case отклоняет
  попытку, не только UI); выбор влияет на модель, которой генерируются
  ответы этого пользователя при каждом следующем сообщении, не
  затрагивает других пользователей; без выбора используется
  `LLM_PROVIDER_DEFAULT_MODEL`.

`.env` и `.env.local` поддерживаются оба, `.env.local` имеет приоритет
(см. `src/dekoder/shared/config.py`); ни один из них не коммитится.

## База данных и миграции

Постоянное хранилище — SQLite через SQLAlchemy 2.x (async, `aiosqlite`);
строка подключения читается из `DATABASE_URL` (`.env.example`, по
умолчанию `sqlite+aiosqlite:///./data/app.db`). Схема базы данных
создаётся и изменяется **только** через Alembic — `Base.metadata.
create_all()` нигде не вызывается в рабочем коде (только в тестовых
фикстурах). Шесть ревизий:

- `alembic/versions/a96ab72bfa8a_create_users_conversations_messages.py`
  (Sprint 2) — создаёт таблицы `users` → `conversations` → `messages` с
  внешними ключами, `CHECK`-ограничениями (роль сообщения, непустой
  текст) и частичным уникальным индексом `uq_conversations_active_user`
  (не более одного активного диалога на пользователя);
- `alembic/versions/14bf7e3ae815_create_profiles_user_active_profiles.py`
  (Sprint 3, S3-03) — создаёт таблицы `profiles` → `user_active_profiles`
  с частичным уникальным индексом `uq_profiles_is_default` (не более
  одного профиля-дефолта в каталоге);
- `alembic/versions/27c4e9f2a103_seed_profile_catalog.py` (Sprint 3,
  S3-04) — data migration, вносит 4 предустановленных профиля через
  `op.bulk_insert` с детерминированными UUID; `downgrade()` удаляет ровно
  эти 4 строки по `id`;
- `alembic/versions/161899ea36c0_create_memory_records.py` (Sprint 5,
  S5-04) — создаёт таблицу `memory_records` (владелец, текст факта,
  категория/источник/статус/значимость через `String`+`CheckConstraint`,
  признак чувствительности, срок действия, автор изменения) с индексом
  `(user_id, status)`, ускоряющим `MemoryRepository.find_relevant`/
  `list_confirmed_by_user`; **без** сид-данных (ADR-5.7) — в отличие от
  `profiles`, память исключительно пользовательские данные, растущие
  только через `/remember`;
- `alembic/versions/82d9884e32a2_create_knowledge_documents.py` (Sprint 6,
  S6-04) — создаёт таблицу `knowledge_documents` (только метаданные
  документа — заголовок, тип, checksum, статус, теги; текст/векторы
  фрагментов не персистятся в SQLite, единственный источник истины —
  Qdrant) с уникальным индексом по `checksum` (дедупликация); **без**
  сид-данных — заполняется только через `scripts/index_document.py`;
- `alembic/versions/ed5701d2f683_create_user_active_models.py` (Sprint 7,
  S7-04, ADR-7.5) — создаёт таблицу `user_active_models` (`user_id` —
  одновременно первичный и внешний ключ, `model_id`, `selected_at`) —
  прямой аналог `user_active_profiles`; **без** сид-данных (ADR-7.4:
  сам каталог моделей — статичный файл `catalog.json`, не БД).

Sprint 8 (административные функции) не добавляет новой ревизии — схема
`profiles`/`knowledge_documents` уже содержала всё необходимое для admin
CRUD с момента её создания (ADR-8.7), включая `status = 'archived'` для
`profiles` (`ck_profiles_status`, разрешено с S3-03). Подтверждено
эмпирически: `alembic upgrade head → downgrade -1 → upgrade head` внутри
Docker-контейнера при финальной интеграции Sprint 8 (S8-11) — те же
шесть ревизий до и после.

```powershell
# Применить все миграции (создаёт/обновляет схему БД) — идемпотентно,
# повторный запуск на уже актуальной схеме ничего не ломает
uv run alembic upgrade head

# Откатить последнюю миграцию / все миграции
uv run alembic downgrade -1
uv run alembic downgrade base

# Посмотреть текущую применённую ревизию
uv run alembic current

# Посмотреть историю миграций
uv run alembic history

# Убедиться, что ORM-модели и применённая схема не разошлись
uv run alembic check

# Создать новую миграцию по изменениям ORM-моделей (autogenerate)
uv run alembic revision --autogenerate -m "краткое описание изменения"
```

Каталог для файла SQLite (`./data/`) при необходимости создаётся
автоматически при старте приложения (`bootstrap/database.py`) — сам файл
БД и таблицы приложение не создаёт, только Alembic (запустите `alembic
upgrade head` перед первым стартом приложения — см. «Быстрый старт»
выше). **Это касается только локального некотейнерного запуска** — в
Docker-развёртывании (`docker compose up`) миграции применяются
автоматически одноразовым сервисом `migrate`, вручную запускать `alembic
upgrade head` не нужно и не требуется (Sprint 11, S11-04, ADR-11.4, см.
разделы «Production-развёртывание»/«Docker» ниже). Каждое новое SQLite-соединение получает `PRAGMA foreign_keys=ON`
централизованно (`infrastructure/persistence/engine.py`) — внешние ключи
между `users`/`conversations`/`messages` реально проверяются на уровне
БД, а не только в приложении.

## Переменные окружения

Полный список с комментариями — в [`.env.example`](.env.example).
Группы настроек (`src/dekoder/shared/config.py`), каждая читает свой
префикс переменных:

| Группа | Префикс | Обязательные (секреты) | Есть значения по умолчанию |
|---|---|---|---|
| `ApplicationSettings` | `APP_` | — | `APP_NAME`, `APP_ENVIRONMENT`, `APP_DEBUG`, `APP_HOST`, `APP_PORT`, `APP_LOG_LEVEL` (Sprint 11, S11-04, ADR-11.5 — гранулярный уровень логирования; `APP_DEBUG=true` продолжает безусловно форсировать `DEBUG` независимо от этого значения) |
| `TelegramSettings` | `TELEGRAM_` | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` | — |
| `LLMSettings` | `LLM_` | — | `LLM_TIMEOUT`, `LLM_MAX_TOKENS`, `LLM_TEMPERATURE` |
| `LLMProviderSettings` | `LLM_PROVIDER_` | `LLM_PROVIDER_API_KEY`, `LLM_PROVIDER_BASE_URL`, `LLM_PROVIDER_DEFAULT_MODEL` (Sprint 11, ADR-11.1 — дженерик-провайдер без универсального дефолта) | `LLM_PROVIDER_PROVIDER_ID` (по умолчанию `custom`) |
| `DatabaseSettings` | `DATABASE_` | — | `DATABASE_URL` |
| `PromptSettings` | `PROMPT_` | — | `PROMPT_TOKEN_BUDGET` (эвристический бюджет `TokenBudgetPolicy`, ADR-4.4) |
| `MemorySettings` | `MEMORY_` | — | `MEMORY_MAX_RELEVANT_RECORDS` (лимит `MemoryRepository.find_relevant`, по умолчанию 5, ADR-5.6) |
| `EmbeddingProviderSettings` | `EMBEDDING_PROVIDER_` | `EMBEDDING_PROVIDER_API_KEY` | `EMBEDDING_PROVIDER_BASE_URL` (по умолчанию — прямой OpenAI), `EMBEDDING_PROVIDER_EMBEDDING_MODEL` (провайдер эмбеддингов RAG, Sprint 6, ADR-6.3, параметризовано в Sprint 12, ADR-12.1) |
| `QdrantSettings` | `QDRANT_` | — | `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_COLLECTION_NAME`, `QDRANT_VECTOR_SIZE` |
| `KnowledgeSettings` | `KNOWLEDGE_` | — | `KNOWLEDGE_MAX_FILE_SIZE_BYTES`, `KNOWLEDGE_CHUNK_SIZE`, `KNOWLEDGE_CHUNK_OVERLAP`, `KNOWLEDGE_SEARCH_LIMIT`, `KNOWLEDGE_MIN_RELEVANCE_SCORE`, `KNOWLEDGE_STORAGE_PATH` |
| `ModelCatalogSettings` | `MODEL_CATALOG_` | — | `MODEL_CATALOG_CATALOG_PATH` (путь к `catalog.json`, по умолчанию сид-файл внутри пакета, Sprint 7, ADR-7.4) |
| `AdminSettings` | `ADMIN_` | `ADMIN_API_KEY` | `ADMIN_HEALTH_CHECK_TIMEOUT` (таймаут одного probe `GET /admin/health` в секундах, по умолчанию 3.0, Sprint 8, ADR-8.3/8.9) |

Отсутствие обязательного секрета в окружении останавливает процесс при
создании `Settings()` (fail-fast), а не на первом запросе.

`DOMAIN` и `RETENTION_DAYS` (Sprint 11, S11-04/S11-05) в этой таблице
намеренно отсутствуют — они не читаются `shared/config.py`/`Settings()`
вообще, ни одна из групп выше их не подхватывает. `DOMAIN` подставляется
самим Caddy (`docker-compose.prod.yml`/`deploy/Caddyfile`), `RETENTION_DAYS`
читается только `deploy/backup.sh` — оба заданы прямо в `.env.example` в
отдельном блоке «Deployment (production only)», подробности — раздел
«Production-развёртывание» ниже.

`ADMIN_API_KEY` — статичный ключ, который клиент передаёт в заголовке
`X-Admin-Api-Key` на любой `/admin/*` эндпоинт (не login/session/JWT —
единственная admin-учётка для MVP). Сравнивается через
`secrets.compare_digest` (защита от timing-атак); ни ожидаемое, ни
переданное значение никогда не попадают в логи (`shared/logging.py::
_SENSITIVE_KEYS`).

### Каталог AI-моделей

`infrastructure/model_catalog/catalog.json` — статичный сид-файл
(Sprint 7, ADR-7.4), 6 записей в конвенции id `vendor/model-name`
(например, `openai/gpt-4o-mini`) — это конвенция OpenRouter, оставленная
как иллюстративный дефолт (Sprint 11, ADR-11.2), а не проверяемый
формат: `ModelId` (`domain/conversation/value_objects.py`) — format-
agnostic value object, код нигде не валидирует форму строки, она
отправляется как есть в поле `model` запроса к `LLM_PROVIDER_BASE_URL`.

**При смене `LLM_PROVIDER_BASE_URL` на другого реального агрегатора
отредактируйте `model_id` каждой записи `catalog.json` вручную** под id
моделей, реально поддерживаемые выбранным сервисом — ничто в коде не
делает это автоматически и не предупреждает заранее. Несоответствие
проявится не при старте приложения, а только на первом сообщении с этой
моделью — адаптер получит ошибку от LLM-провайдера, которая превратится
в `LLM_PROVIDER_CLIENT_ERROR`/`LLM_PROVIDER_MALFORMED_RESPONSE`
(`shared/errors.py`), с понятным пользователю сообщением, но без
проактивной проверки.

## Admin API

Защищённый REST API администрирования (Sprint 8, `presentation/api/`) —
доступен только на процессе `api` (`uvicorn dekoder.main:app`), не на
`telegram-bot`. Каждый запрос обязан нести заголовок `X-Admin-Api-Key`
со значением `ADMIN_API_KEY` — без него или с неверным значением любой
`/admin/*` эндпоинт отвечает `401`. Публичный `GET /health` (без auth,
без сети) не входит в этот раздел и не изменился ни строкой.

Документы базы знаний (`prefix /admin/documents`):

| Метод | Путь | Действие | Код успеха |
|---|---|---|---|
| `POST` | `/admin/documents` | Загрузить и проиндексировать документ (`multipart/form-data`: `file`, `title?`, `tags?`, `description?`) | `201` |
| `GET` | `/admin/documents` | Список всех документов каталога (все статусы, включая `FAILED`/`UNSUPPORTED`) | `200` |
| `GET` | `/admin/documents/{document_id}` | Статус/детали одного документа | `200` / `404` |
| `DELETE` | `/admin/documents/{document_id}` | Удалить документ (векторы → файл → запись); идемпотентно | `204` |
| `POST` | `/admin/documents/{document_id}/reindex` | Переиндексировать уже загруженный документ без повторной загрузки файла | `200` / `404` |

Профили (`prefix /admin/profiles`):

| Метод | Путь | Действие | Код успеха |
|---|---|---|---|
| `GET` | `/admin/profiles` | Список всех профилей каталога (включая архивные) | `200` |
| `POST` | `/admin/profiles` | Создать новый профиль (всегда `is_system=false`, `is_default=false`) | `201` |
| `GET` | `/admin/profiles/{profile_id}` | Детали одного профиля | `200` / `404` |
| `PATCH` | `/admin/profiles/{profile_id}` | Частично изменить профиль (`is_default`/`is_system`/`status` не принимаются) | `200` / `404` |
| `POST` | `/admin/profiles/{profile_id}/archive` | Архивировать профиль | `200` / `404` / `409` (попытка архивировать профиль по умолчанию) |

Здоровье внешних сервисов:

| Метод | Путь | Действие | Код успеха |
|---|---|---|---|
| `GET` | `/admin/health` | Реальные проверки доступности Qdrant/LLM-провайдера/OpenAI | `200` (всегда — `all_healthy=false`, не `5xx`, если сервисы недоступны) |

Пример запроса:

```powershell
curl -H "X-Admin-Api-Key: $env:ADMIN_API_KEY" http://localhost:8000/admin/documents
curl -H "X-Admin-Api-Key: $env:ADMIN_API_KEY" http://localhost:8000/admin/health
```

Тот же функционал доступен через CLI без HTTP/auth-слоя, теми же
билдерами use case'ов, что и REST (единая точка истины сборки,
`bootstrap/knowledge_container.py`):

```powershell
uv run python scripts/index_document.py index <файл> [--title ...] [--tags a,b,c] [--description ...]
uv run python scripts/index_document.py list
uv run python scripts/index_document.py reindex <document_id>
uv run python scripts/index_document.py delete <document_id>
uv run python scripts/check_services.py   # exit code 0, если все три сервиса здоровы, иначе 1
```

`scripts/check_services.py` не проверяет `ADMIN_API_KEY` — CLI-скрипты и
так требуют доступа к `.env`/файловой системе сервера.

Каталог AI-моделей (Sprint 7) остаётся статичным `catalog.json` —
admin CRUD для моделей и admin-доступ к долговременной памяти
(`MemoryRecord` других пользователей) сознательно не входят в Sprint 8
(скоуп-решения №2/№3, `claude.md` §32/§36).

## Проверка качества кода

Обязательны перед завершением любой задачи (`claude.md`, §27):

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

С покрытием:

```powershell
uv run pytest --cov=dekoder --cov-report=term-missing
```

Или всё сразу через pre-commit:

```powershell
pre-commit run --all-files
```

## Тесты

```text
tests/
├── unit/            # domain, application use cases (включая admin: profile CRUD,
│                    #   knowledge list/get/reindex, CheckExternalServicesHealthUseCase),
│                    #   presentation-мапперы/require_admin_api_key, health-check адаптеры, shared
├── integration/     # OpenAiCompatibleLLMAdapter через respx, /health endpoint, Alembic-миграции,
│                    #   репозитории/persistence-потоки ProcessUserMessage/StartNewConversation/
│                    #   ClearConversation/ProfileRepository (включая admin CRUD)/MemoryRepository/
│                    #   KnowledgeDocumentRepository (включая list_all)/ModelSelectionRepository/
│                    #   ConfigModelCatalogRepository поверх временной SQLite (без сети);
│                    #   presentation/api/ — test_admin_documents.py/test_admin_profiles.py/
│                    #   test_admin_health.py/test_error_handlers.py — через реальный
│                    #   create_application() lifespan (OpenAI/LLM-провайдер — respx, Qdrant — fake-клиент
│                    #   или respx-перехват реального REST-эндпоинта, см. докстринги файлов)
└── e2e/             # test_admin_scenario.py (Sprint 8, S8-11) — один continuous-прогон через
                     #   реальный create_application() lifespan: auth на всех трёх admin-роутерах,
                     #   полный цикл документа (upload→list→get→reindex→delete→404), полный цикл
                     #   профиля (create→patch→archive, включая 409 на попытке архивировать
                     #   is_default=True), health-check (здоровый/нездоровый сценарий);
                     # test_conversation_scenario.py — сквозной сценарий диалога поверх реального
                     #   telegram.ext.Application (in-memory fake-репозитории);
                     # test_conversation_persistence_scenario.py — те же сценарии (первое/второе
                     #   сообщение, /new, /clear, изоляция пользователей, перезапуск приложения,
                     #   ошибка LLM, ошибка БД/rollback) поверх РЕАЛЬНОЙ временной SQLite;
                     # test_profile_scenario.py (Sprint 3, S3-09) — дефолтный профиль без выбора,
                     #   переключение влияет только на будущие сообщения, изоляция пользователей,
                     #   отказ на неизвестный profile_id, полный цикл /profile через реальный
                     #   CallbackQueryHandler — поверх РЕАЛЬНОЙ временной SQLite;
                     # test_prompt_engine_scenario.py (Sprint 4, S4-08) — собранный системный промпт
                     #   реально содержит секцию активного профиля; искусственно длинный диалог
                     #   реально обрезается TokenBudgetPolicy, ответ пользователю всё равно приходит
                     #   — поверх РЕАЛЬНОЙ временной SQLite и реального telegram.ext.Application;
                     # test_memory_scenario.py (Sprint 5, S5-07) — /remember сохраняет и виден в
                     #   /memory с кнопкой удаления; пустой текст/пустой список; удаление через
                     #   inline-кнопку; пользователь A не может удалить запись пользователя B даже
                     #   подделав callback_data; /forget не зарегистрирован — поверх РЕАЛЬНОЙ
                     #   временной SQLite;
                     # test_memory_prompt_scenario.py (Sprint 5, S5-08) — «Сценарий 4» §18.4
                     #   «Плана реализации.md» буквально: /remember → /new → сообщение →
                     #   собранный system_prompt содержит факт; изоляция памяти между
                     #   пользователями; /clear и /new не удаляют memory_records; редакция
                     #   чувствительных записей в логах поверх РЕАЛЬНОГО
                     #   SQLAlchemyMemoryRepository (не fake) — поверх РЕАЛЬНОЙ временной SQLite;
                     # test_model_selection_scenario.py (Sprint 7, S7-08) — /model → выбор модели →
                     #   LLMRequest.model_id/temperature/max_tokens соответствуют выбору и
                     #   default_generation_settings боевой модели каталога; откат на умолчание при
                     #   выборе, впоследствии помеченном UNAVAILABLE (лог отката подтверждён через
                     #   capsys+JSON-парсинг, не только «не упало»); изоляция между пользователями;
                     #   полный цикл /model → клавиатура с пометкой «(недоступна)» → выбор через
                     #   реальный CallbackQueryHandler → подтверждение с обновлённой клавиатурой;
                     #   попытка выбрать UNAVAILABLE-модель отклонена и видна пользователю — поверх
                     #   РЕАЛЬНОЙ временной SQLite и реального боевого catalog.json (не fixture)
```

Ни один тест не обращается к реальному Telegram API, реальному сетевому
LLM или реальному Qdrant/OpenAI — единственные подмены всюду
`FakeLLMProvider`/`respx`/fake `KnowledgeSearchService`.

## Docker

Один образ приложения (`Python 3.11 slim`, непривилегированный
пользователь) — два сервиса, каждый со своей командой запуска, плюс
отдельный сервис Qdrant (Sprint 6):

- **`api`** — `uvicorn dekoder.main:app`, порт `8000`, healthcheck на `/health`;
- **`telegram-bot`** — `python -m dekoder.telegram_main` (long polling), без открытого порта;
- **`qdrant`** — `qdrant/qdrant:v1.19.0`, порт `6333`, хранилище векторов базы знаний
  (`dekoder_qdrant_data`, отдельный именованный volume от `dekoder_data`).

`catalog.json` (статичный каталог AI-моделей, Sprint 7) устанавливается
вместе с пакетом (`pip install .`, `pyproject.toml::package-data`) — не
требует отдельного volume/`COPY`, как и Alembic-миграции/`scripts/`.

Внутри compose-сети сервис `api` видит Qdrant по имени сервиса
(`QDRANT_HOST=qdrant`, переопределяется в `docker-compose.yml` поверх
дефолтного `localhost` в `.env`) — на этом основан `GET /admin/health`
(Sprint 8): подтверждено эмпирически при финальной интеграции (S8-11)
реальным запросом изнутри контейнера с реальными `LLM_PROVIDER_API_KEY`/
`EMBEDDING_PROVIDER_API_KEY`, все три сервиса вернулись `healthy: true`.

Секреты не хранятся в `docker-compose.yml` и не копируются в образ —
только через `env_file: .env` (создать из `.env.example`, сам `.env` не коммитится).

```powershell
cp .env.example .env   # заполнить реальными значениями, не коммитится
docker compose build
docker compose up
docker compose down
```

Это базовый (development/локально-проверочный) сценарий — сервис `api`
публикует `:8000` напрямую на хост, HTTPS нет, лимитов ресурсов и ротации
логов нет. Для production-развёртывания (публичный домен, HTTPS через
Caddy, лимиты ресурсов, ротация логов) применяется дополнительно
`docker-compose.prod.yml` — см. раздел «Production-развёртывание» ниже.

## Production-развёртывание

Production-развёртывание (Sprint 11, S11-04, ADR-11.5) поднимает тот же
образ и тот же базовый `docker-compose.yml`, что и раздел «Docker» выше,
плюс оверлей `docker-compose.prod.yml` (Caddy/HTTPS, лимиты ресурсов,
ротация логов) — применяется вместе с базовым файлом, никогда отдельно.

### Предпосылки

- сервер с установленным Docker и Docker Compose v2 (`docker compose
  version` — `condition: service_completed_successfully` у сервиса
  `migrate` требует Compose v2, не устаревший `docker-compose` v1);
- публичное доменное имя, указывающее на IP этого сервера (для реального
  HTTPS через Let's Encrypt) — для локальной проверки без реального
  домена можно использовать `DOMAIN=localhost` (см. ниже);
- открытые на сервере порты `80` и `443` (Caddy получает/обновляет
  сертификат через ACME HTTP-01 на `80`, отдаёт трафик на `443`) —
  входящий доступ к `:8000` в проде не требуется и не используется:
  `docker-compose.prod.yml` убирает прямую публикацию этого порта.

### Запуск

```powershell
cp .env.example .env
# Заполнить реальными значениями: TELEGRAM_BOT_TOKEN, LLM_PROVIDER_API_KEY/
# BASE_URL/DEFAULT_MODEL, EMBEDDING_PROVIDER_API_KEY, ADMIN_API_KEY, APP_LOG_LEVEL
# (по умолчанию INFO — достаточно для прода), DOMAIN (публичное доменное
# имя сервера или localhost для локальной проверки), опционально
# RETENTION_DAYS (см. раздел «Резервное копирование и восстановление»).

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Автоматические миграции (сервис `migrate`)

И базовый `docker-compose.yml`, и прод-оверлей поднимают одноразовый
сервис `migrate` (`alembic upgrade head`, `restart: "no"`) перед тем, как
`api`/`telegram-bot` начнут принимать трафик — оба долгоживущих сервиса
объявлены зависимыми от его успешного завершения
(`depends_on: migrate: condition: service_completed_successfully`), это
устраняет гонку конкурентных `ALTER TABLE`, если бы оба сервиса сами
запускали миграции параллельно в один и тот же SQLite-файл. **Ручной
`alembic upgrade head` перед `docker compose up` больше не нужен** — это
касается только Docker-развёртывания (базового и production); для
локального некотейнерного запуска инструкция в разделе «Быстрый старт»
не изменилась, миграции по-прежнему нужно применять вручную.

### HTTPS через Caddy

`caddy` (`deploy/Caddyfile`) — единственная точка входа `443`/`80` в
проде, проксирует на `api:8000` внутри compose-сети; Admin API больше не
достижим напрямую по `:8000` с хоста (`docker-compose.prod.yml`
переопределяет `api.ports` в пустой список).

- **Реальный домен** (`DOMAIN=example.com`, публично резолвится на IP
  сервера) — Caddy автоматически получает и обновляет сертификат Let's
  Encrypt, без ручного шага;
- **`DOMAIN=localhost`** (или любой другой non-public host) — Caddy
  вместо Let's Encrypt выпускает сертификат через собственный внутренний
  CA (локально доверенный, не настоящий публичный сертификат) — удобно
  для проверки HTTPS-пути на своём сервере без реального домена, но не
  заменяет реальный прод: `curl -k` (пропуская проверку CA) — единственный
  способ обратиться к такому серверу без ручной установки корневого
  сертификата Caddy в доверенные.

### Лимиты ресурсов и ротация логов

`docker-compose.prod.yml` задаёт для `api`/`telegram-bot`
(`cpus: "1.0"`/`memory: 512M`) и `qdrant` (`cpus: "2.0"`/`memory: 1024M`)
жёсткие лимиты ресурсов (`deploy.resources.limits`, применяются Compose v2
CLI вне Swarm-режима) — предотвращают классический MVP-провал «один
процесс съел всю память сервера» ценой OOM-килла именно переросшего
лимит контейнера, а не всей машины. Логирование всех трёх долгоживущих
сервисов переключено на `json-file` с ротацией (`max-size: "10m"`,
`max-file: "3"`, то есть не более ~30 МБ логов на сервис) — без этого
логи по умолчанию растут неограниченно и могут забить диск сервера.

## Резервное копирование и восстановление

Резервное копирование (Sprint 11, S11-05, ADR-11.6) работает на уровне
двух Docker named volumes через одноразовые `alpine`-контейнеры —
`deploy/backup.sh`/`deploy/restore.sh` не импортируют и не запускают код
`dekoder` (категориально отделены от `scripts/`, которые вызывают
`dekoder.*` use case'ы напрямую).

- **`dekoder_data`** — покрывает **три** из шести пунктов §19.5 «Плана
  реализации.md» одним архивом: SQLite-файл (`app.db`) **и** загруженные
  документы базы знаний (`KnowledgeSettings.storage_path`, физически
  внутри `/app/data` — того же volume) **и** активные профили/долговременная
  память (тоже строки в том же SQLite) — одного архива достаточно, потому
  что все три физически лежат в одном месте;
- **`dekoder_qdrant_data`** — векторное хранилище Qdrant (эмбеддинги базы
  знаний, четвёртый пункт §19.5), отдельный архив;
- конфигурационные шаблоны и Alembic-миграции копируются в тот же бандл
  как файлы (`.env.example`, `docker-compose*.yml`, `alembic/`,
  `alembic.ini`) — для офлайн-восстановления «с нуля» на новом сервере
  без отдельного клонирования репозитория (миграции уже версионируются в
  git, копия в бэкапе — не второй механизм версионирования).

Реальное имя каждого Docker volume — `<имя-compose-проекта>_dekoder_data`/
`<имя-compose-проекта>_dekoder_qdrant_data` (стандартное правило Compose);
оба скрипта вычисляют его сами через `docker compose config`, не
хардкодят `dekoder_data`/`dekoder_qdrant_data`.

```powershell
# Из корня репозитория, там же, где docker-compose.yml:
./deploy/backup.sh                              # → backups/<TIMESTAMP>/
RETENTION_DAYS=7 ./deploy/backup.sh              # + удаляет бэкапы старше 7 дней
./deploy/restore.sh backups/<TIMESTAMP>          # восстановление
```

> **`deploy/restore.sh` — разрушительная операция.** Она останавливает
> весь стек (`docker compose down`) и **удаляет** оба named volume
> (`dekoder_data`/`dekoder_qdrant_data`, под их фактическими,
> специфичными для compose-проекта именами — см. выше) со всем их текущим
> содержимым, прежде чем наполнить их заново из архивов бэкапа. Запускайте только
> тогда, когда вы осознанно хотите заменить текущие данные содержимым
> бэкапа (реальное аварийное восстановление или подготовленный
> проверочный прогон на тестовом стенде) — не на проде «просто чтобы
> посмотреть, как это работает».

После `./deploy/restore.sh` поднимите стек заново (`docker compose up
-d`) и проверьте `docker compose exec api alembic current` (та же
ревизия, что до катастрофы) и `GET /admin/health`/`/admin/documents`.

Автоматизация через cron (пример — ежедневно в 03:00, хранить 7 дней):

```cron
0 3 * * * cd /opt/dekoder && RETENTION_DAYS=7 ./deploy/backup.sh
```

Процедура восстановления **реально выполнена end-to-end** (не только
описана) при разработке Sprint 11 (S11-05): поднят стек → загружен
тестовый документ и создан диалог → `backup.sh` → `docker compose down -v`
(намеренное уничтожение volumes) → `restore.sh` → `docker compose up -d`
→ подтверждены `alembic current`, наличие документа в
`GET /admin/documents` и то, что вопрос по факту из документа находит
RAG-контекст (подтверждает восстановление именно Qdrant-данных, не только
SQLite).

## CI/CD

`.github/workflows/ci.yml` (Sprint 11, S11-06, ADR-11.7) — два job'а:

- **`verify`** — `checkout` → `astral-sh/setup-uv` → `uv sync --frozen
  --extra dev` → `ruff format --check` → `ruff check` → `mypy src` →
  unit-тесты → ожидание готовности сервис-контейнера `qdrant/qdrant:v1.19.0`
  → integration-тесты (**реально** против этого Qdrant, не `SKIPPED`) →
  e2e-тесты;
- **`build-image`** — `needs: verify` (не запускается, если `verify`
  упал), собирает production-образ (`docker build .`), без публикации в
  registry.

Секреты GitHub Actions не требуются ни одному шагу — тесты полностью
самодостаточны (реальные внешние LLM/embedding-вызовы везде замоканы
`respx`, `Settings()` в тестах заполняется через `monkeypatch.setenv`),
это тот же инвариант, что и локальный `uv run pytest`. Автоматический
production-деплой из CI сознательно не реализован — §19.6 «Плана
реализации.md» явно не требует этого для MVP; деплой на сервер (см.
раздел «Production-развёртывание» выше) выполняется вручную.

## Основные команды Telegram

| Команда | Действие |
|---|---|
| `/start` | Приветственное сообщение, ничего не создаёт в базе |
| `/new` | Закрывает текущий диалог и начинает новый с чистой историей (старый диалог и его сообщения не удаляются, просто перестают быть активными); память не трогает |
| `/clear` | Удаляет всю историю текущего активного диалога, сам диалог (тот же `conversation_id`) остаётся активным; память не трогает |
| `/profile` | Показывает каталог профилей с inline-клавиатурой, текущий активный отмечен; выбор меняет системную инструкцию для будущих сообщений этого пользователя |
| `/remember <текст>` | Сохраняет факт о пользователе сразу подтверждённым (без двухшагового сценария, ADR-5.9) |
| `/memory` | Показывает подтверждённые факты пользователя с кнопкой 🗑 на каждой записи для удаления (команды `/forget` нет — удаление только через inline-кнопку, ADR-5.10) |
| `/model` | Показывает статичный каталог AI-моделей с inline-клавиатурой, недоступные помечены «(недоступна)»; выбор влияет на модель, которой генерируются ответы этого пользователя |
| *(любой текст без `/`)* | Обычное сообщение — уходит в `ProcessUserMessage`, ответ генерируется настроенным `LLM_PROVIDER_*`-провайдером |

Список проверен по факту регистрации обработчиков в
`presentation/telegram/bot.py` (`build_telegram_application`/
`register_*_handlers`) — других Telegram-команд в проекте не
зарегистрировано.

## Диагностика типовых ошибок

| Симптом | Причина | Решение |
|---|---|---|
| `sqlite3.OperationalError: no such table ...` при первом сообщении/запросе | Миграции не применены | Docker: проверьте `docker compose logs migrate` — сервис должен завершиться кодом 0 до старта `api`/`telegram-bot`; локально: `uv run alembic upgrade head` (см. «База данных и миграции») |
| Ответы бота не содержат ссылок на документы базы знаний, хотя корпус проиндексирован (пустой RAG-контекст) | Qdrant недоступен | Ищите в логах `qdrant_collection_unavailable_at_startup` (Qdrant был недоступен при старте приложения — деградация, не падение) или `qdrant_search_failed` (сбой конкретного поиска); проверьте `docker compose ps qdrant` (`healthy`?) и что `QDRANT_HOST=qdrant` виден процессу внутри compose-сети |
| В логах `api`/`telegram-bot` — `LLM_PROVIDER_UNAUTHORIZED` или `LLM_PROVIDER_CLIENT_ERROR` (`shared/errors.py`) | Неверный `LLM_PROVIDER_BASE_URL` и/или `LLM_PROVIDER_API_KEY` | Проверьте значения в `.env` против документации выбранного агрегатора; `LLM_PROVIDER_UNAUTHORIZED` — ключ неверный/просрочен, `LLM_PROVIDER_CLIENT_ERROR` — часто несовместимый `model` id (см. раздел «Каталог AI-моделей» — при смене агрегатора `catalog.json` нужно отредактировать вручную) |
| Caddy не выпускает сертификат, HTTPS недоступен | DNS не указывает на сервер или порты 80/443 закрыты файрволом | `docker compose logs caddy` — типичная ошибка ACME-валидации; убедитесь, что `DOMAIN` реально резолвится на IP сервера и `80`/`443` открыты снаружи (для локальной проверки без домена используйте `DOMAIN=localhost`, см. «Production-развёртывание») |
| `docker compose ps` показывает `telegram-bot` как `unhealthy` | `TELEGRAM_BOT_TOKEN` невалиден/просрочен | Проверьте `docker compose logs telegram-bot` — если лог `telegram_polling_started` не появился, `Application.initialize()` (в т.ч. вызов `getMe`) не завершился успешно; проверьте значение `TELEGRAM_BOT_TOKEN` в `.env` через [@BotFather](https://t.me/BotFather) |

## Разработка

Правила именования веток, коммитов и общий рабочий процесс — в
[`CONTRIBUTING.md`](CONTRIBUTING.md). Архитектурные принципы,
границы MVP и план спринтов — в [`claude.md`](claude.md).
