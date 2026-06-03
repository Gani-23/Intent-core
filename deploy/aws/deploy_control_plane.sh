#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/docker/control.aws.env}"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker/compose.control.yml}"
PROFILE="${PROFILE:-postgres}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing env file: ${ENV_FILE}" >&2
  exit 1
fi

cd "${ROOT_DIR}"

find "${ROOT_DIR}" -name '._*' -delete

docker compose \
  --profile "${PROFILE}" \
  --env-file "${ENV_FILE}" \
  -f "${COMPOSE_FILE}" \
  up -d --build

docker compose \
  --profile "${PROFILE}" \
  --env-file "${ENV_FILE}" \
  -f "${COMPOSE_FILE}" \
  ps
