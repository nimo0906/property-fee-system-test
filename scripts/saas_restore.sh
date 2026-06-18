#!/usr/bin/env bash
set -euo pipefail
if [ $# -ne 1 ]; then
  echo "usage: scripts/saas_restore.sh /path/to/backup.sql" >&2
  exit 2
fi
docker compose exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB" < "$1"
