#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")/.."
BASE_URL="${ACCEPTANCE_BASE_URL:-http://127.0.0.1:5001}"
NODE_BIN="${NODE_BIN:-/Users/nimo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
NODE_MODS="${NODE_MODS:-/Users/nimo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules}"

echo "== 1/4 Python syntax check =="
PYTHONPYCACHEPREFIX=/private/tmp/property_acceptance_pycache python3 -m py_compile server/*.py server.py desktop_app.py desktop_runtime.py scripts/*.py

echo "== 2/4 Desktop asset check =="
python3 scripts/desktop_release_check.py >/tmp/property_desktop_release_check.log
cat /tmp/property_desktop_release_check.log

echo "== 3/4 HTTP/page acceptance check ($BASE_URL) =="
python3 scripts/acceptance_check.py --base-url "$BASE_URL" --report acceptance-report.json

echo "== 4/4 Browser UI acceptance check ($BASE_URL) =="
if [ -x "$NODE_BIN" ] && [ -d "$NODE_MODS" ]; then
  NODE_PATH="$NODE_MODS" "$NODE_BIN" scripts/browser_acceptance_check.js
else
  echo "SKIP browser acceptance: bundled Node runtime not found."
fi

echo "全部自动验收检查通过。"
