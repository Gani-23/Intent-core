#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker/compose.control.yml}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/docker/control.postgres.env.example}"
API_URL="${API_URL:-http://127.0.0.1:8000}"
CHANGED_BY="${CHANGED_BY:-operator}"
REASON="${REASON:-postgres operational validation}"
KEEP_UP=0
SKIP_BUILD=0
KEEP_ARTIFACTS=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --api-url) API_URL="$2"; shift 2 ;;
    --changed-by) CHANGED_BY="$2"; shift 2 ;;
    --reason) REASON="$2"; shift 2 ;;
    --keep-up) KEEP_UP=1; shift ;;
    --keep-artifacts) KEEP_ARTIFACTS=1; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

set -a
source "$ENV_FILE"
set +a

API_KEY="${LSA_API_KEY:-}"
if [[ -z "$API_KEY" ]]; then
  echo "LSA_API_KEY must be set." >&2
  exit 1
fi

compose() {
  docker compose --profile postgres --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

cleanup() {
  if [[ $KEEP_UP -eq 0 ]]; then
    compose down -v
  fi
}

trap cleanup EXIT

UP_ARGS=(up -d)
if [[ $SKIP_BUILD -eq 0 ]]; then
  UP_ARGS+=(--build)
fi
compose "${UP_ARGS[@]}"

for _ in $(seq 1 60); do
  if python3 - "$API_URL/health" <<'PY'
import json, sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception:
    raise SystemExit(1)
raise SystemExit(0 if payload.get("status") == "ok" else 1)
PY
  then
    break
  fi
  sleep 2
done

RESULT_JSON="$(python3 - "$API_URL/maintenance/control-plane-operational-validation" "$API_KEY" "$CHANGED_BY" "$REASON" "$KEEP_ARTIFACTS" <<'PY'
import json
import sys
import urllib.request

url, api_key, changed_by, reason, keep_artifacts = sys.argv[1:]
cleanup = keep_artifacts != "1"
request = urllib.request.Request(
    url,
    data=json.dumps(
        {
            "changed_by": changed_by,
            "expected_backend": "postgres",
            "reason": reason,
            "process_backups": True,
            "cleanup": cleanup,
            "run_queue_validation": True,
            "run_workload_validation": True,
            "queue_success_jobs": 3,
            "queue_failure_jobs": 1,
            "queue_delay_seconds": 0.0,
            "run_inline_queue_worker": True,
            "workload_rounds": 3,
            "workload_maintenance_pause_jobs": 3,
            "inject_maintenance_mode_pause": True,
        }
    ).encode("utf-8"),
    headers={"Content-Type": "application/json", "X-API-Key": api_key},
    method="POST",
)
with urllib.request.urlopen(request, timeout=30) as response:
    sys.stdout.write(response.read().decode("utf-8"))
PY
)"

echo "$RESULT_JSON"

python3 - "$RESULT_JSON" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
if payload.get("status") != "passed":
    raise SystemExit(f"operational validation failed: {payload.get('status')!r}")
for key, value in payload.get("checks", {}).items():
    if not value:
        raise SystemExit(f"operational validation check failed: {key}")
workload = payload.get("workload_validation") or {}
if workload.get("status") != "passed":
    raise SystemExit(f"workload validation failed: {workload.get('status')!r}")
PY

WORKLOAD_PROOF_JSON="$(python3 - "$API_URL/maintenance/live-workload-drift-proof" "$API_KEY" "$CHANGED_BY" "$REASON" <<'PY'
import json
import sys
import urllib.request

url, api_key, changed_by, reason = sys.argv[1:]
request = urllib.request.Request(
    url,
    data=json.dumps(
        {
            "changed_by": changed_by,
            "reason": f"{reason}: live workload drift proof",
            "persist": True,
        }
    ).encode("utf-8"),
    headers={"Content-Type": "application/json", "X-API-Key": api_key},
    method="POST",
)
with urllib.request.urlopen(request, timeout=60) as response:
    sys.stdout.write(response.read().decode("utf-8"))
PY
)"

echo "$WORKLOAD_PROOF_JSON"

python3 - "$WORKLOAD_PROOF_JSON" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
if not payload.get("passed"):
    raise SystemExit("live workload drift proof failed")
if payload.get("target_mode") != "external":
    raise SystemExit(f"live workload drift proof did not use external targets: {payload.get('target_mode')!r}")
if int(payload.get("alert_count", 0)) < 1:
    raise SystemExit("live workload drift proof did not produce a drift alert")
if "malicious.example.com" not in payload.get("unexpected_targets", []):
    raise SystemExit("live workload drift proof did not capture malicious target")
PY

echo "Postgres operational validation completed successfully."
