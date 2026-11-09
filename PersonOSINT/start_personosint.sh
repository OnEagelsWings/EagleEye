#!/usr/bin/env sh
# EagleEye PersonOSINT starten (Linux/macOS)
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Erster Start: richte Python-Umgebung ein ..."
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/python -m pip install -r requirements.txt
fi
exec .venv/bin/python -m personosint "$@"
