#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export HF_HOME="${HF_HOME:-$PWD/work/cache/huggingface}"
if .venv/bin/python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8765/api/recordings", timeout=1)' >/dev/null 2>&1; then
  open http://127.0.0.1:8765
  exit 0
fi
echo "Keep this window open. Press Control-C to stop the local server."
.venv/bin/python -m liturgy_lab.cli serve --port 8765 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT INT TERM
.venv/bin/python - <<'PY'
import time, urllib.request
for attempt in range(50):
    try:
        urllib.request.urlopen('http://127.0.0.1:8765/api/recordings',timeout=1)
        break
    except OSError:
        time.sleep(.1)
else:
    raise SystemExit('Server did not start. Check the terminal output.')
PY
open http://127.0.0.1:8765
wait "$SERVER_PID"
