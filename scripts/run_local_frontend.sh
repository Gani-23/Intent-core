#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gani/Desktop/Intent-drive/living-systems-auditor"
APP_DIR="$ROOT/dashboard"
PORT="${PORT:-1234}"
BACKEND_PORT="${BACKEND_PORT:-3614}"
TESTING=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="${2:?missing value for --port}"
      shift 2
      ;;
    --backend-port)
      BACKEND_PORT="${2:?missing value for --backend-port}"
      shift 2
      ;;
    --testing)
      TESTING=1
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

cd "$APP_DIR"

if [[ "$TESTING" -eq 1 ]]; then
  export VITE_TESTING_MODE=1
fi

npm install
exec npm run dev -- --host 127.0.0.1 --port "$PORT"
