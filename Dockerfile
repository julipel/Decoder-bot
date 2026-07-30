# Один образ для двух сервисов (api, telegram-bot) — команда процесса
# задаётся в docker-compose.yml, не здесь (см. README, раздел «Docker»).
FROM python:3.11-slim

# Без этого stdout Python полностью буферизуется, когда не подключён к
# TTY (обычный случай в контейнере) — структурированные логи (structlog
# пишет в stdout через print()) реально копятся во внутреннем буфере и
# не долетают до `docker compose logs`, пока буфер не заполнится или
# процесс не завершится. Обнаружено вручную: у telegram-bot полностью
# пустой журнал, хотя у api (uvicorn пишет в stderr, он небуферизован
# по умолчанию) — логи были.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Только рантайм-зависимости из pyproject.toml (без dev-группы).
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# Непривилегированный пользователь — процесс не должен работать от root.
RUN useradd --create-home --uid 1000 dekoder
USER dekoder

EXPOSE 8000

# Значение по умолчанию — сервис api; telegram-bot переопределяет
# command в docker-compose.yml.
CMD ["uvicorn", "dekoder.main:app", "--host", "0.0.0.0", "--port", "8000"]
