#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gani/Desktop/Intent-drive/living-systems-auditor"
APP_DIR="$ROOT/targets/express-pair"
LOG_DIR="$ROOT/data/local_target_logs"
PID_FILE="$LOG_DIR/express-target-pair.pid"
LOG_FILE="$LOG_DIR/express-target-pair.log"

mkdir -p "$LOG_DIR"

if [[ -f "$PID_FILE" ]]; then
  existing_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${existing_pid:-}" ]] && kill -0 "$existing_pid" 2>/dev/null; then
    kill "$existing_pid" 2>/dev/null || true
    sleep 1
  fi
  rm -f "$PID_FILE"
fi

cd "$APP_DIR"
npm install
nohup node server.mjs </dev/null >"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"
sleep 2

if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "failed to start local express target pair"
  echo "log:"
  cat "$LOG_FILE"
  exit 1
fi

if ! curl -fsS -X POST http://127.0.0.1:4011/probe/approved -H 'Content-Type: application/json' -d '{}' >/dev/null; then
  echo "approved target probe failed"
  cat "$LOG_FILE"
  exit 1
fi

if ! curl -fsS -X POST http://127.0.0.1:4012/probe/drift -H 'Content-Type: application/json' -d '{}' >/dev/null; then
  echo "drift target probe failed"
  cat "$LOG_FILE"
  exit 1
fi

echo "started local express target pair"
echo "approved: http://127.0.0.1:4011"
echo "drift:    http://127.0.0.1:4012"
echo "pid: $(cat "$PID_FILE")"
