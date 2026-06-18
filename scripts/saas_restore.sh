#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
usage:
  scripts/saas_restore.sh --database /path/to/db/property_saas.sql
  scripts/saas_restore.sh --tenant-files /path/to/tenant-files/customer_files.tar.gz
  scripts/saas_restore.sh --system-files /path/to/system-files/system_files.tar.gz
  scripts/saas_restore.sh --verify-metadata /path/to/backup_dir

Refusing implicit full restore: choose one explicit scope per run.
USAGE
}

if [ $# -ne 2 ]; then
  usage
  exit 2
fi

scope=$1
source_path=$2
if [ ! -e "$source_path" ]; then
  echo "restore source not found: $source_path" >&2
  exit 2
fi

validate_tar_safe() {
  local archive=$1
  local member
  while IFS= read -r member; do
    case "$member" in
      /*|../*|*/../*|*'/..')
        echo "unsafe archive member: $member" >&2
        exit 2
        ;;
    esac
  done < <(tar -tzf "$archive")
}

verify_metadata() {
  local backup_dir=$1
  local manifest="$backup_dir/checksums.sha256"
  local metadata="$backup_dir/metadata.json"
  if [ ! -f "$manifest" ] || [ ! -f "$metadata" ]; then
    echo "missing backup metadata or manifest" >&2
    exit 2
  fi
  if ! grep -q '"kind":"property-saas-backup"' "$metadata" || ! grep -q '"checksums":"checksums.sha256"' "$metadata"; then
    echo "invalid backup metadata" >&2
    exit 2
  fi
  (cd "$backup_dir" && sha256sum -c "checksums.sha256")
}

case "$scope" in
  --database)
    docker compose exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB" < "$source_path"
    ;;
  --tenant-files)
    validate_tar_safe "$source_path"
    target=${SAAS_CUSTOMER_FILES_DIR:-/var/lib/property-saas/tenants}
    mkdir -p "$target"
    tar -C "$target" -xzf "$source_path"
    ;;
  --system-files)
    validate_tar_safe "$source_path"
    target=${SAAS_SYSTEM_FILES_DIR:-/var/lib/property-saas/system}
    mkdir -p "$target"
    tar -C "$target" -xzf "$source_path"
    ;;
  --verify-metadata)
    verify_metadata "$source_path"
    ;;
  *)
    usage
    exit 2
    ;;
esac
