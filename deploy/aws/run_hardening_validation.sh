#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/docker/control.aws.env}"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker/compose.control.yml}"
PROFILE="${PROFILE:-postgres}"
BY="${BY:-operator}"
EXPECTED_BACKEND="${EXPECTED_BACKEND:-postgres}"
REASON="${REASON:-aws hardening validation}"

cd "${ROOT_DIR}"

docker compose \
  --profile "${PROFILE}" \
  --env-file "${ENV_FILE}" \
  -f "${COMPOSE_FILE}" \
  exec -T api \
  lsa run-control-plane-operational-validation \
  --by "${BY}" \
  --expected-backend "${EXPECTED_BACKEND}" \
  --reason "${REASON}"

docker compose \
  --profile "${PROFILE}" \
  --env-file "${ENV_FILE}" \
  -f "${COMPOSE_FILE}" \
  exec -T api \
  lsa control-plane-deployment-readiness

docker compose \
  --profile "${PROFILE}" \
  --env-file "${ENV_FILE}" \
  -f "${COMPOSE_FILE}" \
  exec -T api \
  lsa export-control-plane-observability \
  --by "${BY}" \
  --reason "${REASON} observability export"
