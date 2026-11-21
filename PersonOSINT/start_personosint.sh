#!/usr/bin/env sh
# EagleEye PersonOSINT starten (Linux/macOS)
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Erster Start: richte Python-Umgebung ein ..."
  python3 -m venv .venv
fi
# A failed dependency installation must not make the next start appear ready.
# The marker is written only after pip completed successfully.
if [ ! -f .venv/.requirements-installed ]; then
  echo "Installiere fehlende Python-Abhaengigkeiten ..."
  .venv/bin/python -m pip install -r requirements.txt
  touch .venv/.requirements-installed
fi
exec .venv/bin/python -m personosint "$@"
