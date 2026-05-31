#!/bin/zsh
set -e
cd "$(dirname "$0")"

echo "Building macOS desktop app..."

PYTHON_CMD="${PYTHON_CMD:-python3}"
$PYTHON_CMD -m pip install --upgrade pip
$PYTHON_CMD -m pip install -r requirements.txt
$PYTHON_CMD -m PyInstaller --clean --noconfirm property_fee_system_macos.spec

echo ""
echo "Build completed: dist/物业管理收费系统.app"
echo "Copy the app or the whole dist folder to the user's Mac."
