# Декодер

Персональный AI-ассистент «Декодер». Целевая архитектура и полный
состав возможностей (профили автора, Content Skills, каталог моделей,
Prompt Engine, база знаний с RAG, память диалога, админ-панель) описаны
в [`CLAUDE.md`](claude.md) и в `docs/versions/` — это проектные
документы, а не описание того, что уже запускается.

**Что реально работает сейчас** — вертикальный срез (Sprint 1,
Walking Skeleton):

```text
Telegram → ProcessUserMessage → LLMProvider → OpenRouterLLMAdapter → ответ
```

Пользователь пишет боту в Telegram → сообщение уходит в единственный
пока use case `ProcessUserMessage` → тот вызывает LLM через порт
`LLMProvider` → адаптер `OpenRouterLLMAdapter` обращается к OpenRouter →
ответ модели возвращается пользователю в Telegram. Диалогов, истории,
профилей, памяти, RAG и выбора модели в этом срезе ещё нет — они
добавляются по спринтам (`claude.md`, §33).

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
├── domain/conversation/            # MessageText, ModelId, ProviderId
├── application/conversation/       # DTO, LLMProvider (порт), ProcessUserMessage
├── infrastructure/llm/             # OpenRouterLLMAdapter
├── presentation/telegram/          # /start, обработчик текстовых сообщений
├── bootstrap/                      # container.py, application.py — единственное место сборки
└── shared/                         # config.py, logging.py, errors.py
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
pydantic / pydantic-settings, structlog. SQLite, Qdrant и остальной
стек из `docs/versions/01_requirements_analysis_v2.0.md` относятся к
будущим спринтам и в этом срезе не подключены.

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
pre-commit install

pytest   # должно пройти без реальных секретов — внешние вызовы замоканы
```

Запуск двух процессов (в отдельных терминалах):

```powershell
# Процесс 1 — ASGI API (/health и т.д.)
uv run uvicorn dekoder.main:app --reload

# Процесс 2 — Telegram bot (long polling)
uv run python -m dekoder.telegram_main
```

После этого можно написать боту `/start`, затем любое текстовое
сообщение — оно уйдёт в OpenRouter и ответ модели придёт обратно в чат.

`.env` и `.env.local` поддерживаются оба, `.env.local` имеет приоритет
(см. `src/dekoder/shared/config.py`); ни один из них не коммитится.

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
├── integration/     # OpenRouter adapter через respx, /health endpoint
└── e2e/             # сквозной сценарий диалога поверх всего среза
```

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
