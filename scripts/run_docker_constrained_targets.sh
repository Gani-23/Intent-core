#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/gani/Desktop/Intent-drive/living-systems-auditor"
COMPOSE_FILE="$ROOT/docker/compose.targets.yml"
PROFILES_FILE="$ROOT/data/workload_target_profiles.json"

cd "$ROOT"
docker compose -f "$COMPOSE_FILE" up -d --build

python3 - <<'PY'
import json
from pathlib import Path

path = Path("/Users/gani/Desktop/Intent-drive/living-systems-auditor/data/workload_target_profiles.json")
path.parent.mkdir(parents=True, exist_ok=True)
payload = {"profiles": []}
if path.exists():
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {"profiles": []}
profiles = payload.get("profiles", [])
if not isinstance(profiles, list):
    profiles = []
entries = {}
for entry in profiles:
    if isinstance(entry, dict) and entry.get("name"):
        entries[str(entry["name"]).strip().lower()] = entry
entries["docker-constrained-express-pair"] = {
    "name": "docker-constrained-express-pair",
    "approved_target_base_url": "http://127.0.0.1:4021",
    "drift_target_base_url": "http://127.0.0.1:4022",
    "approved_probe_url": "http://127.0.0.1:4021/probe/approved",
    "drift_probe_url": "http://127.0.0.1:4022/probe/drift",
    "approved_action_url": "http://127.0.0.1:4021/v1/charges",
    "drift_action_url": "http://127.0.0.1:4022/exfil",
    "enabled": True,
    "description": "Docker-constrained local Express target pair with limited CPU/memory for endurance testing."
}
payload = {"profiles": [entries[name] for name in sorted(entries)]}
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

echo "started constrained docker targets"
echo "approved: http://127.0.0.1:4021"
echo "drift:    http://127.0.0.1:4022"
echo "profile:  docker-constrained-express-pair"
docker compose -f "$COMPOSE_FILE" ps
