#!/bin/bash
set -euo pipefail
APP_DATA_DIR="$HOME/Library/Application Support/PropertyFeeSystemData"
ARCHIVE_ROOT="$HOME/Desktop/PropertyFeeSystemDataBackups"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
ARCHIVE_DIR="$ARCHIVE_ROOT/PropertyFeeSystem_before_reset_$TIMESTAMP"

echo "Property Fee System trial data reset"
echo "WARNING: This script is only for trial/demo data."
echo "WARNING: If this Mac contains real business data, close this window now."
echo ""
echo "Data directory: $APP_DATA_DIR"
echo "Backup target: $ARCHIVE_DIR"
echo ""
echo "Type RESET and press Enter to continue:"
read -r CONFIRM
if [ "$CONFIRM" != "RESET" ]; then
  echo "Cancelled. No data was changed."
  echo "Press any key to close..."
  read -n 1 -r _
  exit 0
fi

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
