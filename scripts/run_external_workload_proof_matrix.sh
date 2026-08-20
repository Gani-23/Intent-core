#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BY="${BY:-operator}"
EXPECTED_BACKEND="${EXPECTED_BACKEND:-sqlite}"

run_profile() {
  local profile="$1"
  local reason="$2"
  echo "=== target_profile=${profile} ==="
  ./.venv/bin/lsa run-live-workload-target-profile-validation --profile "$profile" --by "$BY" --reason "$reason target validation"
  ./.venv/bin/lsa run-live-workload-target-profile-drift-proof --profile "$profile" --by "$BY" --reason "$reason drift proof"
  ./.venv/bin/lsa run-live-workload-target-profile-operational-validation --profile "$profile" --by "$BY" --expected-backend "$EXPECTED_BACKEND" --reason "$reason operational validation"
}

run_profile "public-echo-pair" "public echo external proof"
run_profile "public-httpbin-bingo-pair" "public httpbin bingo external proof"
