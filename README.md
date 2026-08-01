# Декодер

Персональный AI-ассистент «Декодер». Целевая архитектура и полный
состав возможностей (профили автора, Content Skills, каталог моделей,
Prompt Engine, база знаний с RAG, память диалога, админ-панель) описаны
в [`CLAUDE.md`](claude.md) и в `docs/versions/` — это проектные
документы, а не описание того, что уже запускается.

**Что реально работает сейчас** — Sprint 1 (Walking Skeleton) и Sprint 2
(постоянное хранилище, диалоги, история) полностью завершены:

```text
Telegram → ProcessUserMessage → LLMProvider → OpenRouterLLMAdapter → ответ
                 │
                 ├── User/Conversation/Message сохраняются в SQLite
                 └── история активного диалога передаётся в LLM целиком

Telegram /new   → StartNewConversation → закрывает текущий диалог, создаёт новый
Telegram /clear → ClearConversation    → удаляет историю, диалог остаётся активным
```

Пользователь пишет боту в Telegram → сообщение уходит в use case
`ProcessUserMessage` → пользователь и его активный диалог находятся или
создаются в SQLite, сообщение пользователя сохраняется → история диалога
читается из базы и передаётся в LLM через порт `LLMProvider` → адаптер
`OpenRouterLLMAdapter` обращается к OpenRouter → ответ модели сохраняется
как сообщение ассистента и возвращается пользователю в Telegram. Команда
`/new` закрывает текущий диалог и начинает новый (старая история не
удаляется, просто перестаёт быть активной); `/clear` удаляет сообщения
текущего диалога, не закрывая и не пересоздавая сам диалог. Профилей,
Prompt Engine, памяти, RAG и выбора модели ещё нет — они добавляются по
следующим спринтам (`claude.md`, §33).

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
│   └── user/                        # User
├── application/
│   ├── conversation/                # DTO, LLMProvider/ConversationRepository/MessageRepository (порты),
│   │                                 #   ProcessUserMessage, StartNewConversation, ClearConversation
│   └── user/                        # UserRepository (порт)
├── infrastructure/
│   ├── llm/                         # OpenRouterLLMAdapter
│   └── persistence/                 # base.py/engine.py/session.py (SQLAlchemy async, S2-01) +
│                                     #   user_orm.py/conversation_orm.py/message_orm.py + mappers.py (S2-02) +
│                                     #   user_repository.py/conversation_repository.py/message_repository.py (S2-03..S2-05)
├── presentation/telegram/           # /start, /new, /clear, обработчик текстовых сообщений, mapper.py, bot.py
├── bootstrap/                       # container.py, application.py, database.py, repositories.py — единственное место сборки
└── shared/                          # config.py, logging.py, errors.py

alembic/                             # первая и единственная миграция Sprint 2 (users/conversations/messages)
```

> В репозитории также существует более крупное, отдельное от этого
> среза дерево-заглушка — `composition/`, `interfaces/`, а также модули
> `ai_core`, `admin`, `profile`, `memory`, `knowledge_base`, `rag`,
> `model_catalog` под `domain/`/`application/`, и
> `infrastructure/model_gateway/`. Это результат более ранней миграции
> по документам `docs/versions/*_v2.0.md`, построенной по другой
> архитектуре (`interfaces/`+`composition/` вместо
> `presentation/`+`bootstrap/`). Реально запускаемое приложение
> (`main.py`, `telegram_main.py`) его не использует — почти весь код
> там оканчивается `raise NotImplementedError`. Реконсиляция двух
> деревьев — сознательно отложенное решение, подробности в
> `claude.md`, §36.

## Технологический стек

Python 3.11+, FastAPI, uvicorn, python-telegram-bot, httpx,
pydantic / pydantic-settings, structlog. С Sprint 2 подключены и
полностью используются SQLAlchemy 2.x (async, `AsyncEngine`/`AsyncSession`),
`aiosqlite` и Alembic — постоянное хранилище `users`/`conversations`/
`messages` (ORM-модели, репозитории, единственная миграция схемы
`alembic/versions/`), с `PRAGMA foreign_keys=ON` для каждого SQLite-
соединения (`infrastructure/persistence/engine.py`).
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
  продолжает его же, с чистой историей.

`.env` и `.env.local` поддерживаются оба, `.env.local` имеет приоритет
(см. `src/dekoder/shared/config.py`); ни один из них не коммитится.

## База данных и миграции

Постоянное хранилище — SQLite через SQLAlchemy 2.x (async, `aiosqlite`);
строка подключения читается из `DATABASE_URL` (`.env.example`, по
умолчанию `sqlite+aiosqlite:///./data/app.db`). Схема базы данных
создаётся и изменяется **только** через Alembic — `Base.metadata.
create_all()` нигде не вызывается в рабочем коде (только в тестовых
фикстурах). Единственная на сегодня миграция (`alembic/versions/
a96ab72bfa8a_create_users_conversations_messages.py`) создаёт таблицы
`users` → `conversations` → `messages` с внешними ключами, `CHECK`-
ограничениями (роль сообщения, непустой текст) и частичным уникальным
индексом `uq_conversations_active_user` (не более одного активного
диалога на пользователя).

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
│                    #   ClearConversation поверх временной SQLite (без сети)
└── e2e/             # test_conversation_scenario.py — сквозной сценарий диалога поверх реального
                     #   telegram.ext.Application (in-memory fake-репозитории);
                     # test_conversation_persistence_scenario.py — те же сценарии (первое/второе
                     #   сообщение, /new, /clear, изоляция пользователей, перезапуск приложения,
                     #   ошибка LLM, ошибка БД/rollback) поверх РЕАЛЬНОЙ временной SQLite
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
