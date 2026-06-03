#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BY="${BY:-operator}"
EXPECTED_BACKEND="${EXPECTED_BACKEND:-sqlite}"
REASON="${REASON:-customer target live workload proof}"

if [[ -n "${PROFILE:-}" ]]; then
  ./.venv/bin/lsa run-live-workload-target-profile-validation --profile "$PROFILE" --by "$BY" --reason "$REASON target validation"
  ./.venv/bin/lsa run-live-workload-target-profile-drift-proof --profile "$PROFILE" --by "$BY" --reason "$REASON drift proof"
  ./.venv/bin/lsa run-live-workload-target-profile-operational-validation --profile "$PROFILE" --by "$BY" --expected-backend "$EXPECTED_BACKEND" --reason "$REASON operational validation"
elif [[ -n "${LSA_WORKLOAD_PROOF_APPROVED_BASE_URL:-}" && -n "${LSA_WORKLOAD_PROOF_DRIFT_BASE_URL:-}" ]]; then
  export LSA_WORKLOAD_PROOF_TARGET_PROFILE="${LSA_WORKLOAD_PROOF_TARGET_PROFILE:-custom-external-pair}"
  ./.venv/bin/lsa run-control-plane-live-workload-target-validation --by "$BY" --reason "$REASON target validation"
  ./.venv/bin/lsa run-live-workload-drift-proof --by "$BY" --reason "$REASON drift proof"
  ./.venv/bin/lsa run-control-plane-operational-validation --by "$BY" --expected-backend "$EXPECTED_BACKEND" --reason "$REASON operational validation"
else
  echo "Set PROFILE or both LSA_WORKLOAD_PROOF_APPROVED_BASE_URL and LSA_WORKLOAD_PROOF_DRIFT_BASE_URL" >&2
  exit 1
fi

./.venv/bin/lsa export-live-workload-proof-bundle --by "$BY" --reason "$REASON bundle export"
