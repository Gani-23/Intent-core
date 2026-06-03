#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gani/Desktop/Intent-drive/living-systems-auditor"
ENV_FILE="$ROOT/.env.local"

cd "$ROOT"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

ulimit -n 8192 || true

exec ./.venv/bin/python -m uvicorn lsa.api.main:app --host 127.0.0.1 --port 8000
