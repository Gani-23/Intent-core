#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BY="${BY:-operator}"
REASON="${REASON:-public external live workload proof}"
PROFILE="${LSA_WORKLOAD_PROOF_TARGET_PROFILE:-public-echo-pair}"

./.venv/bin/lsa run-live-workload-target-profile-validation --profile "$PROFILE" --by "$BY" --reason "$REASON target validation"
./.venv/bin/lsa run-live-workload-target-profile-drift-proof --profile "$PROFILE" --by "$BY" --reason "$REASON"
./.venv/bin/lsa control-plane-live-workload-proof-validation
