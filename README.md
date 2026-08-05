# Декодер

Персональный AI-ассистент «Декодер». Целевая архитектура и полный
состав возможностей (профили автора, Content Skills, каталог моделей,
Prompt Engine, база знаний с RAG, память диалога, админ-панель) описаны
в [`CLAUDE.md`](claude.md) и в `docs/versions/` — это проектные
документы, а не описание того, что уже запускается.

**Что реально работает сейчас** — Sprint 1 (Walking Skeleton), Sprint 2
(постоянное хранилище, диалоги, история), Sprint 3 (пользовательские
профили), Sprint 4 (Prompt Engine — централизованная сборка промпта) и
Sprint 5 (долговременная память) полностью завершены:

```text
Telegram → ProcessUserMessage → (профиль + память + история) → PromptContext → PromptBuilder → PromptBuildResult
                 │                                                                                   │
                 ├── User/Conversation/Message сохраняются в SQLite                                  │
                 └───────────────────────────────────────────────────── LLMProvider → OpenRouterLLMAdapter → ответ

Telegram /new      → StartNewConversation → закрывает текущий диалог, создаёт новый (память не трогает)
Telegram /clear    → ClearConversation    → удаляет историю, диалог остаётся активным (память не трогает)
Telegram /profile  → ListProfiles/GetActiveProfile/SelectProfile → выбор профиля через inline-клавиатуру
Telegram /remember → CreateMemoryRecordUseCase → сохраняет факт сразу подтверждённым (status=CONFIRMED)
Telegram /memory   → ListMemoryRecordsUseCase → список подтверждённых фактов с inline-удалением (🗑)
```

Пользователь пишет боту в Telegram → сообщение уходит в use case
`ProcessUserMessage` → пользователь и его активный диалог находятся или
создаются в SQLite, читается его активный профиль (`ProfileRepository`) и
до `MemorySettings.max_relevant_records` (по умолчанию 5) подтверждённых
записей памяти (`MemoryRepository.find_relevant` — только `CONFIRMED`, не
истёкшие, отсортированные по значимости и свежести, Sprint 5), сообщение
пользователя сохраняется → история диалога читается из базы →
`ProcessUserMessage` собирает `PromptContext` (профиль + подтверждённая
память + история) и передаёт его `PromptBuilder` (Prompt Engine, Sprint 4)
— тот детерминированно собирает системную инструкцию из 8 фиксированных
секций (базовая инструкция, правила безопасности, параметры активного
профиля — используются ВСЕ описательные поля профиля, не только
`system_instruction`, — подтверждённая память (заполнена реальными
данными с Sprint 5; пустой плейсхолдер RAG), история диалога, текущий
запрос, требования к формату ответа), исключая пустые секции и
ограничивая суммарный объём эвристическим `TokenBudgetPolicy` (обрезает
старую историю первой, если она есть; текущий запрос и системные секции
неприкосновенны) → адаптер `OpenRouterLLMAdapter` обращается к
OpenRouter → ответ модели сохраняется как сообщение ассистента и
возвращается пользователю в Telegram; версии использованных шаблонов
промпта доступны в `ProcessUserMessageResult.prompt_template_versions`.
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
(`user_id`-изоляция на уровне `MemoryRepository`, не только Telegram-слоя).
Персональных (не каталожных) профилей, `CreateProfile`/`UpdateProfile`/
`DeactivateProfile`, RAG и выбора модели ещё нет — они добавляются по
следующим спринтам/этапам (`claude.md`, §33); секция 5 (RAG) Prompt
Engine уже структурно готова, но всегда пуста до соответствующего
спринта. Автоматическое извлечение фактов AI из диалога не реализовано и
не планируется в MVP (§13.2 «Плана реализации.md») — память растёт
только через явную команду `/remember`.

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
│   └── memory/                      # MemoryRecord, MemoryCategory/MemorySource/MemoryStatus/MemoryConfidence (Sprint 5, S5-02)
├── application/
│   ├── conversation/                # DTO, LLMProvider/ConversationRepository/MessageRepository/ConversationRepositories (порты),
│   │                                 #   ProcessUserMessage, StartNewConversation, ClearConversation
│   ├── user/                        # UserRepository (порт)
│   ├── profile/                     # ProfileRepository (порт), DTO, ListProfiles/GetActiveProfile/SelectProfile (S3-05/S3-06)
│   ├── prompt/                      # PromptBuilder/PromptTemplateRepository (порты, S4-03);
│   │                                 #   services/prompt_builder.py::DeterministicPromptBuilder (S4-05),
│   │                                 #   services/token_budget.py::estimate_size (S4-06)
│   └── memory/                      # MemoryRepository (порт, S5-03), DTO, use_cases/ — CreateMemoryRecord/
│                                     #   ConfirmMemoryRecord/RejectMemoryRecord/ListMemoryRecords/DeleteMemoryRecord (S5-05)
├── infrastructure/
│   ├── llm/                         # OpenRouterLLMAdapter
│   ├── persistence/                 # base.py/engine.py/session.py (SQLAlchemy async, S2-01) +
│   │                                 #   user_orm.py/conversation_orm.py/message_orm.py + mappers.py (S2-02) +
│   │                                 #   user_repository.py/conversation_repository.py/message_repository.py (S2-03..S2-05) +
│   │                                 #   profile_orm.py/user_active_profile_orm.py/profile_repository.py (Sprint 3, S3-03/S3-05) +
│   │                                 #   memory_record_orm.py/memory_repository.py::SQLAlchemyMemoryRepository (Sprint 5, S5-04)
│   └── prompts/                     # file_template_repository.py::FileTemplateRepository +
│                                     #   templates/{manifest.json, *.txt} — 6 сид-шаблонов (Sprint 4, S4-04)
├── presentation/telegram/           # /start, /new, /clear, /profile, /remember, /memory (S5-07),
│                                     #   обработчик текстовых сообщений, mapper.py, bot.py
├── bootstrap/                       # container.py, application.py, database.py, repositories.py — единственное место сборки
└── shared/                          # config.py, logging.py, errors.py

alembic/                             # users/conversations/messages (S2-02) + profiles/user_active_profiles (S3-03) +
                                      #   сид-каталог из 4 профилей (S3-04) + memory_records, схема без сид-данных
                                      #   (Sprint 5, S5-04, ADR-5.7) — Sprint 4 не добавляет миграций
                                      #   (шаблоны промпта — файловое хранилище, не БД, ADR-4.2)
```

> В репозитории также существует более крупное, отдельное от этого
> среза дерево-заглушка — `composition/`, `interfaces/`, а также модули
> `ai_core`, `admin`, `memory`, `knowledge_base`, `rag`, `model_catalog`
> под `domain/`/`application/`, и `infrastructure/model_gateway/`. Это
> результат более ранней миграции по документам
> `docs/versions/*_v2.0.md`, построенной по другой архитектуре
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
> memory_collector.py`) был удалён в Sprint 5 (задача S5-01) по той же
> логике — прямой риск путаницы именно в момент, когда строилась
> настоящая долговременная память (`domain/memory/`, `application/
> memory/`, реальная форма `MemoryRecord`). Остальной v2.0-скелет
> (`admin`, `rag`, `session`, `skills`, `model_catalog`, `knowledge_base`,
> `model_gateway`, `infrastructure/vector_storage`, `interfaces/`,
> `composition/`) по-прежнему не тронут — признан нежизнеспособным, но
> его зачистка вынесена в отдельную будущую задачу (ADR-4.10/ADR-5.1).

## Технологический стек

Python 3.11+, FastAPI, uvicorn, python-telegram-bot, httpx,
pydantic / pydantic-settings, structlog. С Sprint 2 подключены и
полностью используются SQLAlchemy 2.x (async, `AsyncEngine`/`AsyncSession`),
`aiosqlite` и Alembic — постоянное хранилище `users`/`conversations`/
`messages` (ORM-модели, репозитории, единственная миграция схемы
`alembic/versions/`), с `PRAGMA foreign_keys=ON` для каждого SQLite-
соединения (`infrastructure/persistence/engine.py`).
Prompt Engine (Sprint 4) не добавляет ни одной новой зависимости —
подстановка переменных в шаблоны промпта использует только стандартную
библиотеку (`string.Template`), не Jinja2 и не другой шаблонизатор;
шаблоны хранятся в текстовых файлах за портом, не в БД (ADR-4.2).
Qdrant и остальной стек из `docs/versions/01_requirements_analysis_v2.0.md`
по-прежнему относятся к будущим спринтам и в этом срезе не подключены.

## Быстрый старт (локальная разработка)

Предварительно нужны:

- Python 3.11+;
- [uv](https://docs.astral.sh/uv/);
- токен Telegram-бота (создать через [@BotFather](https://t.me/BotFather));
- API-ключ [OpenRouter](https://openrouter.ai/keys).

```powershell
git clone <URL этого репозитория>
cd Decoder

uv venv
uv pip install -e ".[dev]"

cp .env.example .env.local   # заполнить TELEGRAM_BOT_TOKEN и OPENROUTER_API_KEY
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
схемой `users`/`conversations`/`messages` — см. раздел «База данных и
миграции» ниже):

```powershell
uv run alembic upgrade head
```

После этого можно написать боту `/start`, затем любое текстовое
сообщение — оно уйдёт в OpenRouter, а сам диалог (пользователь, диалог,
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
  отправленные сообщения и не влияет на других пользователей.

`.env` и `.env.local` поддерживаются оба, `.env.local` имеет приоритет
(см. `src/dekoder/shared/config.py`); ни один из них не коммитится.

## База данных и миграции

Постоянное хранилище — SQLite через SQLAlchemy 2.x (async, `aiosqlite`);
строка подключения читается из `DATABASE_URL` (`.env.example`, по
умолчанию `sqlite+aiosqlite:///./data/app.db`). Схема базы данных
создаётся и изменяется **только** через Alembic — `Base.metadata.
create_all()` нигде не вызывается в рабочем коде (только в тестовых
фикстурах). Четыре ревизии:

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
  только через `/remember`.

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
выше). Каждое новое SQLite-соединение получает `PRAGMA foreign_keys=ON`
централизованно (`infrastructure/persistence/engine.py`) — внешние ключи
между `users`/`conversations`/`messages` реально проверяются на уровне
БД, а не только в приложении.

## Переменные окружения

Полный список с комментариями — в [`.env.example`](.env.example).
Группы настроек (`src/dekoder/shared/config.py`), каждая читает свой
префикс переменных:

| Группа | Префикс | Обязательные (секреты) | Есть значения по умолчанию |
|---|---|---|---|
| `ApplicationSettings` | `APP_` | — | `APP_NAME`, `APP_ENVIRONMENT`, `APP_DEBUG`, `APP_HOST`, `APP_PORT` |
| `TelegramSettings` | `TELEGRAM_` | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` | — |
| `LLMSettings` | `LLM_` | — | `LLM_TIMEOUT`, `LLM_MAX_TOKENS`, `LLM_TEMPERATURE` |
| `OpenRouterSettings` | `OPENROUTER_` | `OPENROUTER_API_KEY` | `OPENROUTER_BASE_URL`, `OPENROUTER_DEFAULT_MODEL` |
| `DatabaseSettings` | `DATABASE_` | — | `DATABASE_URL` |
| `PromptSettings` | `PROMPT_` | — | `PROMPT_TOKEN_BUDGET` (эвристический бюджет `TokenBudgetPolicy`, ADR-4.4) |
| `MemorySettings` | `MEMORY_` | — | `MEMORY_MAX_RELEVANT_RECORDS` (лимит `MemoryRepository.find_relevant`, по умолчанию 5, ADR-5.6) |

Отсутствие обязательного секрета в окружении останавливает процесс при
создании `Settings()` (fail-fast), а не на первом запросе.

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
├── unit/            # domain, application use cases, presentation-мапперы, shared
├── integration/     # OpenRouter adapter через respx, /health endpoint, Alembic-миграции,
│                    #   репозитории/persistence-потоки ProcessUserMessage/StartNewConversation/
│                    #   ClearConversation/ProfileRepository поверх временной SQLite (без сети)
└── e2e/             # test_conversation_scenario.py — сквозной сценарий диалога поверх реального
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
                     #   SQLAlchemyMemoryRepository (не fake) — поверх РЕАЛЬНОЙ временной SQLite
```

Ни один тест не обращается к реальному Telegram API или реальному
сетевому LLM — единственная подмена всюду `FakeLLMProvider`/`respx`.

## Docker

Один образ (`Python 3.11 slim`, непривилегированный пользователь) —
два сервиса, каждый со своей командой запуска:

- **`api`** — `uvicorn dekoder.main:app`, порт `8000`, healthcheck на `/health`;
- **`telegram-bot`** — `python -m dekoder.telegram_main` (long polling), без открытого порта.

Секреты не хранятся в `docker-compose.yml` и не копируются в образ —
только через `env_file: .env` (создать из `.env.example`, сам `.env` не коммитится).

```powershell
cp .env.example .env   # заполнить реальными значениями, не коммитится
docker compose build
docker compose up
docker compose down
```

## Разработка

Правила именования веток, коммитов и общий рабочий процесс — в
[`CONTRIBUTING.md`](CONTRIBUTING.md). Архитектурные принципы,
границы MVP и план спринтов — в [`claude.md`](claude.md).
