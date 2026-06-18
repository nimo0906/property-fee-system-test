#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
usage:
  scripts/saas_restore.sh --database /path/to/db/property_saas.sql
  scripts/saas_restore.sh --tenant-files /path/to/tenant-files/customer_files.tar.gz
  scripts/saas_restore.sh --system-files /path/to/system-files/system_files.tar.gz

Refusing implicit full restore: choose one explicit scope per run.
USAGE
}

if [ $# -ne 2 ]; then
  usage
  exit 2
fi

scope=$1
source_path=$2
if [ ! -f "$source_path" ]; then
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
  *)
    usage
    exit 2
    ;;
esac
