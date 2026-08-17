# Один образ для двух сервисов (api, telegram-bot) — команда процесса
# задаётся в docker-compose.yml, не здесь (см. README, раздел «Docker»).

# --- Стадия builder: собирает виртуальное окружение через uv --------------
# `uv.lock` — источник истины и для локальной разработки, и здесь: `--frozen`
# запрещает uv пересчитывать резолвер при сборке, устраняя дрейф версий
# между «работает у меня» и продом (ADR-11.3).
FROM python:3.11-slim AS builder

# Тег `0.11` — минорный пин, синхронизированный с локальной версией
# разработки (`uv 0.11.19`, проверено `uv --version`). При обновлении
# локального uv — обновить и этот тег.
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# Отдельный слой только с манифестами зависимостей — кэшируется независимо
# от изменений в src/, инвалидируется только при правке pyproject.toml/
# uv.lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Установка самого пакета (включая package-data — шаблоны Prompt Engine и
# catalog.json, см. pyproject.toml::[tool.setuptools.package-data]; `uv sync`
# собирает пакет через тот же build-backend (setuptools), что и раньше
# `pip install .` — секция package-data остаётся релевантной).
COPY src ./src
RUN uv sync --frozen --no-dev

# --- Стадия runtime: только .venv + исходники, без builder-инструментов ---
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
# PYTHONUNBUFFERED: без этого stdout Python полностью буферизуется, когда
# не подключён к TTY (обычный случай в контейнере) — структурированные логи
# (structlog пишет в stdout через print()) реально копятся во внутреннем
# буфере и не долетают до `docker compose logs`, пока буфер не заполнится
# или процесс не завершится. Обнаружено вручную: у telegram-bot полностью
# пустой журнал, хотя у api (uvicorn пишет в stderr, он небуферизован
# по умолчанию) — логи были.

WORKDIR /app

# Только .venv (рантайм-зависимости, без dev-группы: pytest/ruff/mypy не
# попадают в прод-образ) + src — ни исходников builder-стадии, ни кэша
# pip/uv.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src ./src

# `alembic.ini`/`alembic/` (env.py + versions/) — без них `alembic upgrade
# head` внутри контейнера падает `FAILED: No 'script_location' key found
# in configuration` (обнаружено в задаче S3-09, «Финальная интеграция»:
# ни один процесс/тест до этого реально не запускал alembic ИЗ
# собранного образа — интеграционные/e2e-тесты запускают его с хоста,
# из корня репозитория, где оба файла и так присутствуют). README
# инструктирует применять миграции перед первым запуском (см. «Быстрый
# старт», «База данных и миграции») — этот шаг был невыполним внутри
# Docker-развёртывания без этой правки.
COPY alembic.ini ./
COPY alembic ./alembic

# `scripts/index_document.py` (Sprint 6, задача S6-09/S6-11) — не часть
# устанавливаемого пакета `dekoder` (сборка пакета его не подхватывает,
# как и alembic.ini/alembic/ выше по той же причине, найденной в S3-09):
# без явного COPY `python scripts/index_document.py` внутри контейнера
# падал бы `No such file or directory`.
COPY scripts ./scripts

# Непривилегированный пользователь — процесс не должен работать от root.
# `/app/data` создаётся и передаётся во владение `dekoder` уже здесь, при
# сборке образа: `bootstrap/database.py::_ensure_sqlite_directory_exists`
# (Sprint 2, S2-01) создаёт этот каталог сама при старте, но `/app`
# принадлежит `root` (создан предыдущими `COPY`/`WORKDIR`, ещё от имени
# root) — без явного `chown` непривилегированный `dekoder` не может
# создать в нём подкаталог (`mkdir: Permission denied`), и оба сервиса
# (`api`/`telegram-bot`) падали бы при старте, не успев принять ни одного
# запроса. Обнаружено и исправлено в задаче S2-11 (финальная интеграция) —
# подтверждено вручную сборкой образа и попыткой `mkdir` от лица `dekoder`
# до этого исправления.
RUN useradd --create-home --uid 1000 dekoder \
    && mkdir -p /app/data \
    && chown -R dekoder:dekoder /app/data
USER dekoder

EXPOSE 8000

# Встроенная проверка здоровья образа — раньше жила только в
# docker-compose.yml::api (у telegram-bot её не было вообще). Соответствует
# дефолтной команде (`api`, uvicorn, GET /health) — единственный процесс,
# для которого HTTP-проверка на уровне образа осмысленна; `telegram-bot`
# (переопределяет CMD в compose) получает отдельный healthcheck на уровне
# docker-compose.yml (см. ADR-11.4), не здесь — Dockerfile не может условно
# ветвить HEALTHCHECK по переопределённой команде.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"

# Graceful shutdown — без изменений кода: uvicorn штатно обрабатывает
# SIGTERM (in-flight запросы дорабатывают, новые не принимаются),
# Application.run_polling() (PTB) уже устанавливает обработчики
# SIGINT/SIGTERM/SIGABRT (подтверждено докстрингом telegram_main.py).

# Значение по умолчанию — сервис api; telegram-bot переопределяет
# command в docker-compose.yml.
CMD ["python", "-m", "uvicorn", "dekoder.main:app", "--host", "0.0.0.0", "--port", "8000"]
