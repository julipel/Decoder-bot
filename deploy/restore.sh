#!/usr/bin/env bash
# deploy/restore.sh — восстановление Docker named volumes проекта
# «Декодер» из бэкапа, созданного deploy/backup.sh (Sprint 11, S11-05,
# ADR-11.6).
#
# !!! РАЗРУШИТЕЛЬНАЯ ОПЕРАЦИЯ !!!
# Скрипт останавливает стек (`docker compose down`), УДАЛЯЕТ оба named
# volume (dekoder_data/dekoder_qdrant_data — под фактическими,
# специфичными для compose-проекта именами) со ВСЕМ их текущим
# содержимым и заново наполняет их из архивов бэкапа. Запускать только
# тогда, когда вы осознанно хотите заменить текущие данные содержимым
# бэкапа (реальное аварийное восстановление или подготовленный
# проверочный drill на тестовом стенде) — НЕ на проде "просто чтобы
# посмотреть, как это работает".
#
# Использование: ./deploy/restore.sh <путь-к-каталогу-бэкапа>
# (запускать из корня репозитория, там же, где docker-compose.yml;
# каталог бэкапа — результат deploy/backup.sh, например backups/20260810T120000Z).

set -euo pipefail

BACKUP_DIR="${1:?Использование: deploy/restore.sh <путь-к-каталогу-бэкапа>}"

if [ ! -f docker-compose.yml ]; then
  echo "docker-compose.yml не найден в текущем каталоге — запускайте deploy/restore.sh из корня репозитория." >&2
  exit 1
fi

if [ ! -f "${BACKUP_DIR}/dekoder_data.tar.gz" ] || [ ! -f "${BACKUP_DIR}/dekoder_qdrant_data.tar.gz" ]; then
  echo "В '${BACKUP_DIR}' не найдены dekoder_data.tar.gz/dekoder_qdrant_data.tar.gz — это не каталог, созданный deploy/backup.sh?" >&2
  exit 1
fi

# См. deploy/backup.sh: реальное имя volume = "<имя-compose-проекта>_dekoder_data"/
# "..._dekoder_qdrant_data" — вычисляется, не хардкодится (в этом проекте
# фактически decoder_dekoder_data/decoder_dekoder_qdrant_data).
PROJECT_NAME="$(docker compose config 2>/dev/null | head -1 | sed -E 's/^name:[[:space:]]*//')"
if [ -z "$PROJECT_NAME" ]; then
  echo "Не удалось определить имя compose-проекта (docker compose config)." >&2
  exit 1
fi
DATA_VOLUME="${PROJECT_NAME}_dekoder_data"
QDRANT_VOLUME="${PROJECT_NAME}_dekoder_qdrant_data"

echo "!!! ВНИМАНИЕ: сейчас будут ОСТАНОВЛЕНЫ контейнеры и УДАЛЕНЫ тома ${DATA_VOLUME} и ${QDRANT_VOLUME}."
echo "!!! Всё их текущее содержимое будет БЕЗВОЗВРАТНО потеряно и заменено данными из ${BACKUP_DIR}."

docker compose down

docker volume rm -f "$DATA_VOLUME" "$QDRANT_VOLUME"
docker volume create "$DATA_VOLUME"
docker volume create "$QDRANT_VOLUME"

echo "Восстанавливаю ${DATA_VOLUME} из ${BACKUP_DIR}/dekoder_data.tar.gz..."
docker run --rm -v "${DATA_VOLUME}:/data" -v "$(pwd)/${BACKUP_DIR}:/backup" \
  alpine sh -c "cd /data && tar xzf /backup/dekoder_data.tar.gz"

echo "Восстанавливаю ${QDRANT_VOLUME} из ${BACKUP_DIR}/dekoder_qdrant_data.tar.gz..."
docker run --rm -v "${QDRANT_VOLUME}:/data" -v "$(pwd)/${BACKUP_DIR}:/backup" \
  alpine sh -c "cd /data && tar xzf /backup/dekoder_qdrant_data.tar.gz"

echo "Volumes ${DATA_VOLUME}/${QDRANT_VOLUME} восстановлены из ${BACKUP_DIR}."
echo "Дальнейшие шаги:"
echo "  1. docker compose up -d"
echo "  2. Проверьте GET /health и GET /admin/health (X-Admin-Api-Key)"
echo "  3. Проверьте: docker compose exec api alembic current — ревизия должна совпадать с той, что была до катастрофы"
