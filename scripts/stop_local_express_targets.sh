#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gani/Desktop/Intent-drive/living-systems-auditor"
PID_FILE="$ROOT/data/local_target_logs/express-target-pair.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "local express target pair not running"
  exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
  kill "$pid" 2>/dev/null || true
  sleep 1
fi

rm -f "$PID_FILE"
echo "stopped local express target pair"
