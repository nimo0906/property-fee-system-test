#!/usr/bin/env bash
set -euo pipefail
backup_dir=${1:-./backups}
mkdir -p "$backup_dir"
ts=$(date +%Y%m%d-%H%M%S)
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$backup_dir/property_saas_$ts.sql"
