#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gani/Desktop/Intent-drive/living-systems-auditor"
LOG_DIR="$ROOT/data/soak_runs/background"
PID_FILE="$LOG_DIR/long-soak.pid"
LOG_FILE="$LOG_DIR/long-soak.log"

ITERATIONS="${ITERATIONS:-24}"
PAUSE_SECONDS="${PAUSE_SECONDS:-120}"
EXPECTED_BACKEND="${EXPECTED_BACKEND:-sqlite}"
TARGET_PROFILE="${TARGET_PROFILE:-public-echo-pair}"
BY="${BY:-gani}"
REASON="${REASON:-long backend soak}"
TESTING=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --testing)
      TESTING=1
      shift
      ;;
    --iterations)
      ITERATIONS="${2:?missing value for --iterations}"
      shift 2
      ;;
    --pause-seconds)
      PAUSE_SECONDS="${2:?missing value for --pause-seconds}"
      shift 2
      ;;
    --expected-backend)
      EXPECTED_BACKEND="${2:?missing value for --expected-backend}"
      shift 2
      ;;
    --target-profile)
      TARGET_PROFILE="${2:?missing value for --target-profile}"
      shift 2
      ;;
    --by)
      BY="${2:?missing value for --by}"
      shift 2
      ;;
    --reason)
      REASON="${2:?missing value for --reason}"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "$TESTING" -eq 1 && "${REASON:-}" == "long backend soak" ]]; then
  REASON="testing"
fi

mkdir -p "$LOG_DIR"

if [[ -f "$PID_FILE" ]]; then
  existing_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${existing_pid:-}" ]] && kill -0 "$existing_pid" 2>/dev/null; then
    echo "long soak already running with pid $existing_pid"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

cd "$ROOT"
python3 - <<PY
import os
import subprocess
from pathlib import Path

root = Path("/Users/gani/Desktop/Intent-drive/living-systems-auditor")
log_file = Path("$LOG_FILE")
pid_file = Path("$PID_FILE")

command = [
    str(root / ".venv/bin/python"),
    "-m",
    "lsa.cli.main",
    "run-control-plane-soak-validation",
    "--by",
    "$BY",
    "--expected-backend",
    "$EXPECTED_BACKEND",
    "--reason",
    "$REASON",
    "--target-profile",
    "$TARGET_PROFILE",
    "--iterations",
    "$ITERATIONS",
    "--pause-seconds",
    "$PAUSE_SECONDS",
]

if [[ "$TESTING" -eq 1 ]]; then
    command+=("--testing")
fi

with log_file.open("ab") as handle:
    process = subprocess.Popen(
        command,
        cwd=root,
        stdout=handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env=os.environ.copy(),
    )
pid_file.write_text(str(process.pid), encoding="utf-8")
print(process.pid)
PY

echo "started long soak"
echo "pid: $(cat "$PID_FILE")"
echo "log: $LOG_FILE"
echo "profile: $TARGET_PROFILE"
echo "iterations: $ITERATIONS"
echo "pause_seconds: $PAUSE_SECONDS"
