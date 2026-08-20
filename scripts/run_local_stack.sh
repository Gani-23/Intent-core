#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gani/Desktop/Intent-drive/living-systems-auditor"
BACKEND_PORT="${BACKEND_PORT:-3614}"
FRONTEND_PORT="${FRONTEND_PORT:-1234}"
TESTING=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --testing)
      TESTING=1
      shift
      ;;
    --backend-port)
      BACKEND_PORT="${2:?missing value for --backend-port}"
      shift 2
      ;;
    --frontend-port)
      FRONTEND_PORT="${2:?missing value for --frontend-port}"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

backend_args=(--port "$BACKEND_PORT")
frontend_args=(--port "$FRONTEND_PORT" --backend-port "$BACKEND_PORT")

if [[ "$TESTING" -eq 1 ]]; then
  backend_args+=(--testing)
  frontend_args+=(--testing)
fi

"$ROOT/scripts/run_local_backend.sh" "${backend_args[@]}" &
backend_pid=$!
"$ROOT/scripts/run_local_frontend.sh" "${frontend_args[@]}" &
frontend_pid=$!

cleanup() {
  kill "$backend_pid" "$frontend_pid" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

wait
