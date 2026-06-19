#!/usr/bin/env bash
set -euo pipefail

backup_root=${1:-${SAAS_BACKUP_DIR:-./backups}}
ts=$(date +%Y%m%d-%H%M%S)
backup_dir="$backup_root/$ts"
mkdir -p "$backup_dir/db" "$backup_dir/tenant-files" "$backup_dir/system-files"

docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$backup_dir/db/property_saas.sql"

customer_dir=${SAAS_CUSTOMER_FILES_DIR:-/var/lib/property-saas/tenants}
system_dir=${SAAS_SYSTEM_FILES_DIR:-/var/lib/property-saas/system}
if [ -d "$customer_dir" ]; then
  tar -C "$customer_dir" -czf "$backup_dir/tenant-files/customer_files.tar.gz" .
fi
if [ -d "$system_dir" ]; then
  tar -C "$system_dir" -czf "$backup_dir/system-files/system_files.tar.gz" .
fi

manifest="$backup_dir/checksums.sha256"
: > "$manifest"
if [ -f "$backup_dir/db/property_saas.sql" ]; then
  (cd "$backup_dir" && sha256sum "db/property_saas.sql" >> "$manifest")
fi
if [ -f "$backup_dir/tenant-files/customer_files.tar.gz" ]; then
  (cd "$backup_dir" && sha256sum "tenant-files/customer_files.tar.gz" >> "$manifest")
fi
if [ -f "$backup_dir/system-files/system_files.tar.gz" ]; then
  (cd "$backup_dir" && sha256sum "system-files/system_files.tar.gz" >> "$manifest")
fi

cat > "$backup_dir/metadata.json" <<JSON
{"kind":"property-saas-backup","created_at":"$ts","database":"db/property_saas.sql","tenant_files":"tenant-files/customer_files.tar.gz","system_files":"system-files/system_files.tar.gz","acceptance_records":"first_tenant_acceptance/records.json","checksums":"checksums.sha256"}
JSON
printf 'backup created: %s\n' "$backup_dir"
