#!/bin/bash
set -e
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Install Python 3 from https://www.python.org/downloads/ then try again."
  read -r -p "Press Return to close."
  exit 1
fi
python3 run_viewer.py
