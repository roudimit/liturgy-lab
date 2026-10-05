#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${LITURGY_PYTHON:-python3}"
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3,11), "Use Python 3.11+; set LITURGY_PYTHON=/path/to/python3.12"'
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
echo "Installed in $PWD/.venv. Start with .venv/bin/python -m liturgy_lab.cli serve"
