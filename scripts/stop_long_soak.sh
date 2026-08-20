#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gani/Desktop/Intent-drive/living-systems-auditor"
PID_FILE="$ROOT/data/soak_runs/background/long-soak.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "no long soak pid file"
  exit 0
fi

pid="$(cat "$PID_FILE" 2>/dev/null || true)"
if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
  kill "$pid" 2>/dev/null || true
fi
rm -f "$PID_FILE"
echo "stopped long soak"
