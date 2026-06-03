#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker/compose.control.yml}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/docker/control.postgres.env.example}"
API_URL="${API_URL:-http://127.0.0.1:8000}"
CHANGED_BY="${CHANGED_BY:-operator}"
REASON="${REASON:-postgres failure drills}"
KEEP_UP=0
SKIP_BUILD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --api-url) API_URL="$2"; shift 2 ;;
    --changed-by) CHANGED_BY="$2"; shift 2 ;;
    --reason) REASON="$2"; shift 2 ;;
    --keep-up) KEEP_UP=1; shift ;;
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

wait_for_health() {
  local attempts="${1:-60}"
  for _ in $(seq 1 "$attempts"); do
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
      return 0
    fi
    sleep 2
  done
  echo "API health did not become ready in time." >&2
  exit 1
}

wait_for_active_workers() {
  local attempts="${1:-60}"
  for _ in $(seq 1 "$attempts"); do
    if python3 - "$API_URL/health" "$API_KEY" <<'PY'
import json, sys, urllib.request
url, api_key = sys.argv[1:]
request = urllib.request.Request(url, headers={"X-API-Key": api_key})
try:
    with urllib.request.urlopen(request, timeout=2) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception:
    raise SystemExit(1)
raise SystemExit(0 if int(payload.get("active_workers", 0)) > 0 else 1)
PY
    then
      return 0
    fi
    sleep 2
  done
  echo "No active workers became visible in time." >&2
  exit 1
}

post_json() {
  python3 - "$1" "$API_KEY" "$2" "$3" <<'PY'
import json, sys, urllib.request
url, api_key, payload_json, actor_id = sys.argv[1:]
request = urllib.request.Request(
    url,
    data=payload_json.encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        "X-API-Key": api_key,
        "X-Actor-Id": actor_id,
        "X-Actor-Role": "admin",
    },
    method="POST",
)
with urllib.request.urlopen(request, timeout=60) as response:
    sys.stdout.write(response.read().decode("utf-8"))
PY
}

UP_ARGS=(up -d)
if [[ $SKIP_BUILD -eq 0 ]]; then
  UP_ARGS+=(--build)
fi
compose "${UP_ARGS[@]}"

wait_for_health 90
wait_for_active_workers 90

OP_VALIDATION_PAYLOAD="$(python3 - "$CHANGED_BY" "$REASON" <<'PY'
import json, sys
changed_by, reason = sys.argv[1:]
print(json.dumps({
    "changed_by": changed_by,
    "expected_backend": "postgres",
    "reason": reason,
    "process_backups": True,
    "cleanup": True,
    "run_queue_validation": True,
    "run_workload_validation": True,
    "run_worker_recovery_validation": True,
    "queue_success_jobs": 2,
    "queue_failure_jobs": 1,
    "queue_delay_seconds": 0.0,
    "run_inline_queue_worker": True,
    "workload_rounds": 2,
    "workload_maintenance_pause_jobs": 2,
    "inject_maintenance_mode_pause": True,
}))
PY
)"

OP_RESULT="$(post_json "$API_URL/maintenance/control-plane-operational-validation" "$OP_VALIDATION_PAYLOAD" "$CHANGED_BY")"
echo "$OP_RESULT"

python3 - "$OP_RESULT" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
if payload.get("status") != "passed":
    raise SystemExit(f"operational validation failed: {payload.get('status')!r}")
for key, value in payload.get("checks", {}).items():
    if not value:
        raise SystemExit(f"operational validation check failed: {key}")
PY

compose restart worker
wait_for_health 90
wait_for_active_workers 90

QUEUE_PAYLOAD="$(python3 - "$CHANGED_BY" "$REASON" <<'PY'
import json, sys
changed_by, reason = sys.argv[1:]
print(json.dumps({
    "changed_by": changed_by,
    "reason": f"{reason}: worker restart queue drill",
    "queue_success_jobs": 2,
    "queue_failure_jobs": 1,
    "queue_delay_seconds": 0.0,
    "run_inline_queue_worker": True,
}))
PY
)"

QUEUE_RESULT="$(post_json "$API_URL/maintenance/control-plane-queue-validation" "$QUEUE_PAYLOAD" "$CHANGED_BY")"
echo "$QUEUE_RESULT"

python3 - "$QUEUE_RESULT" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
if payload.get("status") != "passed":
    raise SystemExit(f"queue validation failed after worker restart: {payload.get('status')!r}")
PY

compose restart api
wait_for_health 90
wait_for_active_workers 90

python3 - "$API_URL/maintenance/control-plane-deployment-readiness" "$API_KEY" <<'PY'
import json, sys, urllib.request
url, api_key = sys.argv[1:]
request = urllib.request.Request(url, headers={"X-API-Key": api_key})
with urllib.request.urlopen(request, timeout=30) as response:
    payload = json.loads(response.read().decode("utf-8"))
print(json.dumps(payload, indent=2))
if not payload.get("ready"):
    raise SystemExit("deployment readiness failed after api restart")
PY

OBS_PAYLOAD="$(python3 - "$CHANGED_BY" "$REASON" <<'PY'
import json, sys
changed_by, reason = sys.argv[1:]
print(json.dumps({
    "changed_by": changed_by,
    "reason": f"{reason}: post-restart observability export",
}))
PY
)"

OBS_RESULT="$(post_json "$API_URL/maintenance/control-plane-observability-export" "$OBS_PAYLOAD" "$CHANGED_BY")"
echo "$OBS_RESULT"

python3 - "$OBS_RESULT" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
if payload.get("delivery_state") == "failed":
    raise SystemExit("observability export delivery failed")
PY

LIVE_PROOF_PAYLOAD="$(python3 - "$CHANGED_BY" "$REASON" <<'PY'
import json, sys
changed_by, reason = sys.argv[1:]
print(json.dumps({
    "changed_by": changed_by,
    "reason": f"{reason}: live workload drift proof",
    "persist": True,
}))
PY
)"

LIVE_PROOF_RESULT="$(post_json "$API_URL/maintenance/live-workload-drift-proof" "$LIVE_PROOF_PAYLOAD" "$CHANGED_BY")"
echo "$LIVE_PROOF_RESULT"

python3 - "$LIVE_PROOF_RESULT" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
if not payload.get("passed"):
    raise SystemExit("live workload drift proof failed during failure drills")
if payload.get("target_mode") != "external":
    raise SystemExit(f"live workload drift proof did not use external targets during failure drills: {payload.get('target_mode')!r}")
if int(payload.get("alert_count", 0)) < 1:
    raise SystemExit("live workload drift proof produced no alerts during failure drills")
PY

echo "Postgres failure drills completed successfully."
