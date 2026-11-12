#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)' || {
  echo "EagleEye requires Python 3.12 or newer." >&2
  exit 1
}

# Use XDG-based, persistent external settings/workspace from desktop476.
# Do not redirect case data into the upgradeable installation tree.
"$PYTHON_BIN" INSTALL_EAGLEEYE_490.py
RUNTIME_PY=".eagleeye-runtime-490/bin/python"
if [ ! -x "$RUNTIME_PY" ]; then
  echo "EagleEye runtime is missing after installation." >&2
  exit 1
fi

exec "$RUNTIME_PY" -I -m eagleeye.bootstrap.desktop476 --install-root "$PWD"
