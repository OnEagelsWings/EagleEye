#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)' || {
  echo "EagleEye requires Python 3.12 or newer." >&2
  exit 1
}

"$PYTHON_BIN" INSTALL_EAGLEEYE_453.py
RUNTIME_PY=".eagleeye-runtime/bin/python"
if [ ! -x "$RUNTIME_PY" ]; then
  echo "EagleEye runtime is missing after installation." >&2
  exit 1
fi

export EAGLEEYE_WORKSPACE_ROOT="$PWD"
exec "$RUNTIME_PY" -I -c 'import os; from eagleeye.interfaces.web.server import serve_workspace; raise SystemExit(serve_workspace(base_dir=os.environ["EAGLEEYE_WORKSPACE_ROOT"]))'
