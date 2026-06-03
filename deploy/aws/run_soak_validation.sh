#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

ITERATIONS="${ITERATIONS:-3}"
SLEEP_SECONDS="${SLEEP_SECONDS:-60}"
EXPECTED_BACKEND="${EXPECTED_BACKEND:-postgres}"
ACTOR="${ACTOR:-soak-runner}"
TARGET_PROFILE="${TARGET_PROFILE:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --iterations)
      ITERATIONS="$2"
      shift 2
      ;;
    --sleep-seconds)
      SLEEP_SECONDS="$2"
      shift 2
      ;;
    --expected-backend)
      EXPECTED_BACKEND="$2"
      shift 2
      ;;
    --by)
      ACTOR="$2"
      shift 2
      ;;
    --target-profile)
      TARGET_PROFILE="$2"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$ROOT_DIR/data/soak_runs/$RUN_ID"
mkdir -p "$RUN_DIR"

run_validation() {
  local iteration="$1"
  local reason="aws soak validation iteration ${iteration}/${ITERATIONS}"
  if [[ -n "$TARGET_PROFILE" ]]; then
    docker exec docker-api-1 \
      lsa \
      run-live-workload-target-profile-operational-validation \
      --profile "$TARGET_PROFILE" \
      --by "$ACTOR" \
      --expected-backend "$EXPECTED_BACKEND" \
      --reason "$reason"
    return
  fi
  docker exec docker-api-1 \
    lsa \
    run-control-plane-operational-validation \
    --by "$ACTOR" \
    --expected-backend "$EXPECTED_BACKEND" \
    --reason "$reason"
}

for ((i=1; i<=ITERATIONS; i++)); do
  echo "== soak iteration $i/$ITERATIONS =="
  run_validation "$i" > "$RUN_DIR/operational_validation_${i}.json"
  curl -s http://127.0.0.1:8000/health > "$RUN_DIR/health_${i}.json"
  docker exec docker-api-1 lsa control-plane-deployment-readiness > "$RUN_DIR/deployment_readiness_${i}.json"

  python3 - "$RUN_DIR" "$i" <<'PY'
import json
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
iteration = sys.argv[2]
op = json.loads((run_dir / f"operational_validation_{iteration}.json").read_text())
health = json.loads((run_dir / f"health_{iteration}.json").read_text())
readiness = json.loads((run_dir / f"deployment_readiness_{iteration}.json").read_text())

summary = {
    "iteration": int(iteration),
    "operational_validation_status": op["status"],
    "worker_recovery_validation_status": op["worker_recovery_validation"]["status"],
    "deployment_readiness_ready": readiness["ready"],
    "health_status": health["status"],
    "health_worker_running": health["worker_running"],
    "health_database_backend": health["database_backend"],
}
(run_dir / "summary.jsonl").open("a", encoding="utf-8").write(json.dumps(summary) + "\n")

errors = []
if op["status"] != "passed":
    errors.append("operational validation failed")
if op["worker_recovery_validation"]["status"] != "passed":
    errors.append("worker recovery validation failed")
if not readiness["ready"]:
    errors.append("deployment readiness not ready")
if health["status"] != "ok":
    errors.append("health not ok")
if not health["worker_running"]:
    errors.append("worker not running")

if errors:
    print(json.dumps({"iteration": int(iteration), "errors": errors}, indent=2))
    raise SystemExit(1)

print(json.dumps(summary, indent=2))
PY

  if [[ "$i" -lt "$ITERATIONS" ]]; then
    sleep "$SLEEP_SECONDS"
  fi
done

echo "soak run complete: $RUN_DIR"
