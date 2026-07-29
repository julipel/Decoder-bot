# Декодер

Персональный AI-ассистент «Декодер» — MVP модульного монолита (Clean
Architecture / Ports & Adapters), реализующий единый профиль автора, базу
знаний с поиском (RAG), память диалога и Telegram-интерфейс, с панелью
администратора для управления профилем и содержимым базы знаний.

## Документация

Полное описание требований, архитектуры, доменной модели, внутренних
интерфейсов и окружения разработки — в [`docs/`](docs/):

- [`docs/01_requirements_analysis.md`](docs/01_requirements_analysis.md) — анализ требований
- [`docs/02_system_architecture.md`](docs/02_system_architecture.md) — системная архитектура
- [`docs/03_project_structure.md`](docs/03_project_structure.md) — структура проекта
- [`docs/04_domain_model.md`](docs/04_domain_model.md) — доменная модель
- [`docs/05_internal_interfaces.md`](docs/05_internal_interfaces.md) — внутренние интерфейсы
- [`docs/06_development_environment.md`](docs/06_development_environment.md) — окружение разработки

Предыдущие утверждённые версии этих документов — в [`docs/versions/`](docs/versions/).

## Технологический стек

Python 3.11+, FastAPI, python-telegram-bot, SQLite, Qdrant, structlog.
Полный состав и обоснование выбора — в `docs/01` и `docs/02`.

## Быстрый старт

```powershell
uv venv
uv pip install -e ".[dev]"
cp .env.example .env.local   # заполнить значения локально
pre-commit install
pytest
```

Подробности об окружении, переменных `.env.local` и Docker-окружении — в
[`docs/06_development_environment.md`](docs/06_development_environment.md).

## Проверка качества кода

```powershell
ruff check .        # линт: синтаксис, импорты, стиль, ошибки, упрощения, аннотации, async
ruff format --check .
mypy src
pytest
pre-commit run --all-files
```

## Разработка

Правила именования веток, коммитов и общий рабочий процесс — в
[`CONTRIBUTING.md`](CONTRIBUTING.md).
