#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' || {
  echo "EagleEye requires Python 3.11 or newer." >&2
  exit 1
}

if [ ! -x ".venv/bin/python" ]; then
  echo "First start: creating the local EagleEye Python environment..."
  "$PYTHON_BIN" -m venv .venv
fi

VENV_PY=".venv/bin/python"
if ! "$VENV_PY" -c 'import fastapi, uvicorn, sqlalchemy, pydantic' >/dev/null 2>&1; then
  echo "Installing EagleEye runtime dependencies..."
  "$VENV_PY" -m pip install -e .
fi

exec "$VENV_PY" EAGLEEYE_PRO_416_0.py
