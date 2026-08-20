#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gani/Desktop/Intent-drive/living-systems-auditor"
ENV_FILE="$ROOT/.env.local"
PORT="${PORT:-3614}"
TESTING=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="${2:?missing value for --port}"
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

cd "$ROOT"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [[ "$TESTING" -eq 1 ]]; then
  export LSA_DATABASE_URL="sqlite:///$ROOT/data/control_plane.testing.db"
  export LSA_ENVIRONMENT_NAME="testing"
  export LSA_TESTING_MODE=1
fi

ulimit -n 8192 || true

exec ./.venv/bin/python -m uvicorn lsa.api.main:app --host 127.0.0.1 --port "$PORT"
