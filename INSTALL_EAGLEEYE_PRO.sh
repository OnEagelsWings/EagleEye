#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
exec "$PYTHON_BIN" INSTALL_EAGLEEYE_455.py "$@"
