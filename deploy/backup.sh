#!/usr/bin/env bash
# deploy/backup.sh — резервное копирование Docker named volumes проекта
# «Декодер» (Sprint 11, S11-05, ADR-11.6). Работает исключительно на
# уровне Docker volumes через одноразовый alpine-контейнер — НЕ
# импортирует и не запускает код `dekoder` (категориально отделено от
# `scripts/`, которые вызывают `dekoder.*` use case'ы напрямую).
#
# Покрывает все шесть пунктов §19.5 «Плана реализации.md» двумя архивами:
#   - dekoder_data.tar.gz        — SQLite (app.db) + загруженные документы
#                                  (KnowledgeSettings.storage_path физически
#                                  внутри того же volume, /app/data) +
#                                  активные профили/память (строки в том
#                                  же SQLite) — один архив покрывает три
#                                  из шести пунктов §19.5 сразу.
#   - dekoder_qdrant_data.tar.gz — векторное хранилище Qdrant (эмбеддинги
#                                  базы знаний).
# Плюс копии конфигурационных шаблонов и Alembic-миграций — для offline
# восстановления "с нуля" на новом сервере (миграции уже версионируются
# в git, копия в бэкапе — не новый механизм версионирования, а удобство
# восстановления без отдельного клона репозитория).
#
# Использование: ./deploy/backup.sh   (запускать из корня репозитория,
# там же, где docker-compose.yml).
#
# Переменные окружения:
#   BACKUP_ROOT     — куда складывать бэкапы (по умолчанию ./backups).
#   RETENTION_DAYS  — опционально: удалить каталоги бэкапов старше N дней
#                     внутри BACKUP_ROOT. НЕ задан по умолчанию — без
#                     явного RETENTION_DAYS ни один бэкап не удаляется
#                     автоматически (безопасный дефолт, ADR-11.6).

set -euo pipefail

if [ ! -f docker-compose.yml ]; then
  echo "docker-compose.yml не найден в текущем каталоге — запускайте deploy/backup.sh из корня репозитория." >&2
  exit 1
fi

# Реальное имя Docker volume = "<имя-compose-проекта>_<имя-volume-в-yml>"
# (стандартное правило Compose при отсутствии явного "name:" в разделе
# volumes верхнего уровня). Имя проекта НЕ хардкодится как "dekoder" —
# вычисляется через сам `docker compose config`, чтобы скрипт работал
# независимо от того, как называется каталог клона репозитория/от
# COMPOSE_PROJECT_NAME (в этом проекте фактическое имя проекта — "decoder",
# а тома — decoder_dekoder_data/decoder_dekoder_qdrant_data, не голые
# dekoder_data/dekoder_qdrant_data из иллюстративного примера ADR-11.6 —
# проверено `docker volume ls` перед реализацией, не предположено).
PROJECT_NAME="$(docker compose config 2>/dev/null | head -1 | sed -E 's/^name:[[:space:]]*//')"
if [ -z "$PROJECT_NAME" ]; then
  echo "Не удалось определить имя compose-проекта (docker compose config)." >&2
  exit 1
fi
DATA_VOLUME="${PROJECT_NAME}_dekoder_data"
QDRANT_VOLUME="${PROJECT_NAME}_dekoder_qdrant_data"

TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_ROOT="${BACKUP_ROOT:-./backups}"
BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"
mkdir -p "$BACKUP_DIR"

echo "Compose-проект: ${PROJECT_NAME} (volumes: ${DATA_VOLUME}, ${QDRANT_VOLUME})"

echo "Бэкап ${DATA_VOLUME} (SQLite + загруженные документы: /app/data)..."
docker run --rm -v "${DATA_VOLUME}:/data:ro" -v "$(pwd)/${BACKUP_DIR}:/backup" \
  alpine tar czf /backup/dekoder_data.tar.gz -C /data .

echo "Бэкап ${QDRANT_VOLUME} (векторное хранилище)..."
docker run --rm -v "${QDRANT_VOLUME}:/data:ro" -v "$(pwd)/${BACKUP_DIR}:/backup" \
  alpine tar czf /backup/dekoder_qdrant_data.tar.gz -C /data .

echo "Конфигурационные шаблоны и миграции..."
cp .env.example docker-compose.yml "$BACKUP_DIR/"
[ -f docker-compose.prod.yml ] && cp docker-compose.prod.yml "$BACKUP_DIR/"
cp -r alembic "$BACKUP_DIR/alembic"
cp alembic.ini "$BACKUP_DIR/"

if [ -n "${RETENTION_DAYS:-}" ]; then
  echo "RETENTION_DAYS=${RETENTION_DAYS}: удаляю каталоги бэкапов старше ${RETENTION_DAYS} дней в ${BACKUP_ROOT}..."
  find "$BACKUP_ROOT" -maxdepth 1 -mindepth 1 -type d -mtime "+${RETENTION_DAYS}" -exec rm -rf {} \;
fi

echo "Готово: $BACKUP_DIR"
