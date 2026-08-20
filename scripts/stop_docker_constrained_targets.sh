#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gani/Desktop/Intent-drive/living-systems-auditor"
COMPOSE_FILE="$ROOT/docker/compose.targets.yml"

cd "$ROOT"
docker compose -f "$COMPOSE_FILE" down
echo "stopped constrained docker targets"
