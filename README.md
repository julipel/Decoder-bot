# Декодер

Персональный AI-ассистент «Декодер» — MVP модульного монолита (Clean
Architecture / Ports & Adapters), реализующий несколько профилей автора,
Content Skills, каталог моделей, генерацию контента через Prompt Engine,
базу знаний с поиском (RAG), память диалога и Telegram-интерфейс — с
панелью администратора для управления базой знаний.

## Документация

Действующая архитектура — **версия 2.0** в [`docs/versions/`](docs/versions/):

- [`docs/versions/01_requirements_analysis_v2.0.md`](docs/versions/01_requirements_analysis_v2.0.md) — анализ требований
- [`docs/versions/02_system_architecture_v2.0.md`](docs/versions/02_system_architecture_v2.0.md) — системная архитектура
- [`docs/versions/03_project_structure_v2.0.md`](docs/versions/03_project_structure_v2.0.md) — структура проекта
- [`docs/versions/04_domain_model_v2.0.md`](docs/versions/04_domain_model_v2.0.md) — доменная модель
- [`docs/versions/05_internal_interfaces_v2.0.md`](docs/versions/05_internal_interfaces_v2.0.md) — внутренние интерфейсы
- [`docs/versions/06_development_environment_v2.0.md`](docs/versions/06_development_environment_v2.0.md) — окружение разработки

Документы версии 1.0 в [`docs/`](docs/) (`01`–`06` без суффикса) помечены
недействительными и сохранены только как исторический источник — код
проекта им больше не соответствует.

## Технологический стек

Python 3.11+, FastAPI, python-telegram-bot, SQLite, Qdrant, structlog.
Полный состав и обоснование выбора — в `docs/versions/01_requirements_analysis_v2.0.md`
и `docs/versions/02_system_architecture_v2.0.md`.

## Быстрый старт

```powershell
uv venv
uv pip install -e ".[dev]"
cp .env.example .env.local   # заполнить значения локально
pre-commit install
pytest
```

Подробности об окружении, переменных `.env.local` и Docker-окружении — в
[`docs/versions/06_development_environment_v2.0.md`](docs/versions/06_development_environment_v2.0.md).

## Проверка качества кода

```powershell
ruff check .        # линт: синтаксис, импорты, стиль, ошибки, упрощения, аннотации, async
ruff format --check .
mypy src
pytest
pre-commit run --all-files
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
[`CONTRIBUTING.md`](CONTRIBUTING.md).
