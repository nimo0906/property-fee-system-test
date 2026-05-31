#!/bin/bash
set -euo pipefail
APP_DATA_DIR="$HOME/Library/Application Support/PropertyFeeSystem"
ARCHIVE_ROOT="$HOME/Desktop/PropertyFeeSystemDataBackups"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
ARCHIVE_DIR="$ARCHIVE_ROOT/PropertyFeeSystem_before_reset_$TIMESTAMP"

echo "Property Fee System trial data reset"
echo "Data directory: $APP_DATA_DIR"
echo "Backup target: $ARCHIVE_DIR"
echo ""

if [ ! -d "$APP_DATA_DIR" ]; then
  echo "No existing data directory found. Nothing to reset."
  echo "Press any key to close..."
  read -n 1 -r _
  exit 0
fi

mkdir -p "$ARCHIVE_ROOT"
cp -R "$APP_DATA_DIR" "$ARCHIVE_DIR"
rm -rf "$APP_DATA_DIR"

echo "Existing data has been backed up and reset."
echo "Backup saved at: $ARCHIVE_DIR"
echo "Start the app again to create a clean trial database."
echo ""
echo "Press any key to close..."
read -n 1 -r _
