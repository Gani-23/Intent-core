#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gani/Desktop/Intent-drive/living-systems-auditor"
LOG_FILE="$ROOT/data/soak_runs/background/long-soak.log"

if [[ ! -f "$LOG_FILE" ]]; then
  echo "no long soak log yet"
  exit 0
fi

tail -f "$LOG_FILE"
