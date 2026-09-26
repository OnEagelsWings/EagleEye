#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)' || {
  echo "EagleEye requires Python 3.12 or newer." >&2
  exit 1
}

# Debian/Ubuntu may ship Python without the OS venv/ensurepip component.
# Detect that before leaving a partial .venv behind.
if [ -d ".venv" ] && [ ! -x ".venv/bin/python" ]; then
  echo "Removing incomplete EagleEye virtual environment from an earlier failed start..." >&2
  rm -rf .venv
fi

if [ ! -x ".venv/bin/python" ]; then
  if ! "$PYTHON_BIN" -m venv --help >/dev/null 2>&1; then
    echo "EagleEye cannot create a Python virtual environment with: $PYTHON_BIN" >&2
    echo "Debian/Ubuntu: install the venv package first, e.g.:" >&2
    echo "  sudo apt install python3-venv" >&2
    echo "or the matching versioned package (for example python3.14-venv)." >&2
    exit 1
  fi
  if ! "$PYTHON_BIN" -m ensurepip --version >/dev/null 2>&1; then
    echo "EagleEye first-start prerequisite missing: ensurepip/venv is unavailable." >&2
    echo "Debian/Ubuntu: install it first, e.g.:" >&2
    echo "  sudo apt install python3-venv" >&2
    echo "or the matching versioned package (for example python3.14-venv)." >&2
    echo "Then run ./START_EAGLEEYE_PRO.sh again." >&2
    exit 1
  fi
  echo "First start: creating the local EagleEye Python environment..."
  if ! "$PYTHON_BIN" -m venv .venv; then
    echo "EagleEye could not create .venv. Removing the incomplete environment." >&2
    rm -rf .venv
    exit 1
  fi
fi

VENV_PY=".venv/bin/python"
if ! "$VENV_PY" -c 'import fastapi, uvicorn, sqlalchemy, pydantic' >/dev/null 2>&1; then
  echo "Installing EagleEye runtime dependencies..."
  "$VENV_PY" -m pip install -e .
fi

exec "$VENV_PY" EAGLEEYE_PRO_439_0.py
