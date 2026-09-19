#!/usr/bin/env sh
set -u
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo
echo "EagleEye 15-Minute External Test"
echo "--------------------------------"
echo "Running local preflight. No telemetry is sent."
echo

"$PYTHON_BIN" tools/external_test_preflight.py
STATUS=$?

echo
echo "Read QUICK_TEST.md, then use the normal EagleEye launcher."
echo "Your report is external_test_report.txt."
if [ "$STATUS" -ne 0 ]; then
  echo "Preflight found a blocker. Please report it rather than repairing it for us."
fi
exit "$STATUS"
