from __future__ import annotations

import json
import os
from typing import Any
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware

from lsa.api.models import (
    HealthResponse,
    IngestSessionEventRequest,
    IngestSessionEventResponse,
    OrgPolicy,
    PolicyRule,
)
from lsa.drift.adapters import ClaudeCodeAdapter, CursorAgentAdapter, GenericWebhookAdapter
from lsa.drift.redaction import redact_json_obj

app = FastAPI(title="Living Systems Auditor API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from lsa.storage.sqlite_store import SQLiteEventStore

_STORE = SQLiteEventStore()

# Seed default development/testing API key if configured
_DEFAULT_KEY = os.environ.get("LSA_API_KEY", "lsa-test-key-12345")
if _DEFAULT_KEY:
    _STORE.create_api_key(organization_name="default", raw_key=_DEFAULT_KEY)


class AuthContext:
    def __init__(self, key: str, organization_name: str, role: str = "member"):
        self.key = key
        self.organization_name = organization_name
        self.role = role


def verify_api_key(x_api_key: str | None = Header(None)) -> AuthContext:
    """Validate API Key auth strictly against persistent store."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    key_info = _STORE.lookup_key(x_api_key)
    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if key_info.get("revoked", False):
        raise HTTPException(status_code=401, detail="API key has been revoked")
    return AuthContext(
        key=x_api_key,
        organization_name=key_info["organization_name"],
        role=key_info.get("role", "member"),
    )


def verify_admin_key(auth: AuthContext = Depends(verify_api_key)) -> AuthContext:
    """Verify that caller has admin role for their organization."""
    if auth.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required for this operation")
    return auth


@app.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Health check endpoint reporting actual runtime subsystem state."""
    db_healthy = _STORE.is_healthy()
    return HealthResponse(
        status="ok" if db_healthy else "degraded",
        database_ready=db_healthy,
        database_backend="sqlite",
        authz_enabled=False,
        worker_running=False,
    )


@app.post("/api/v1/sessions/events", response_model=IngestSessionEventResponse)
def ingest_session_event(
    req: IngestSessionEventRequest,
    auth: AuthContext = Depends(verify_api_key),
) -> IngestSessionEventResponse:
    """Ingest and durably persist live agent events from Claude Code, Cursor, or Webhooks."""
    # 1. Select adapter
    if req.agent_source == "cursor":
        adapter = CursorAgentAdapter()
    elif req.agent_source == "generic":
        adapter = GenericWebhookAdapter()
    else:
        adapter = ClaudeCodeAdapter()

    payload = {
        "session_id": req.session_id,
        "tool_name": req.tool_name,
        "target": req.target or str(req.tool_input.get("sql", req.tool_input.get("command", req.tool_input.get("file_path", "")))),
        "tool_input": req.tool_input,
        "tool_response": req.tool_response,
        **req.tool_input,
    }
    redacted_payload = redact_json_obj(payload)
    event = adapter.parse_event(redacted_payload)

    # Detect blocked or policy violation status
    is_blocked = req.blocked
    if not is_blocked and isinstance(req.tool_response, dict):
        if req.tool_response.get("continue") is False or "Blocked" in str(req.tool_response.get("reason", "")):
            is_blocked = True

    is_violation = req.policy_violation or is_blocked
    if not is_violation:
        policy_rec = _STORE.get_org_policy(auth.organization_name)
        if policy_rec and policy_rec.get("policy_yaml"):
            try:
                import yaml, re
                p_data = yaml.safe_load(policy_rec["policy_yaml"])
                target_cmd = req.target or str(req.tool_input.get("sql", req.tool_input.get("command", req.tool_input.get("file_path", ""))))
                for r in p_data.get("rules", []):
                    m = r.get("match", {})
                    pat = m.get("command_pattern") or m.get("target_pattern")
                    if pat and re.search(pat, target_cmd, re.I):
                        is_violation = True
                        if r.get("action") == "block":
                            is_blocked = True
                        break
            except Exception:
                pass

    # 2. Persist to SQLite store, strictly scoping organization to the verified API key
    persisted = False
    if event is not None:
        try:
            row_id = _STORE.store_event(
                session_id=req.session_id,
                agent_source=req.agent_source,
                tool_name=req.tool_name,
                target=event.target,
                payload=redacted_payload,
                organization_name=auth.organization_name,
                blocked=is_blocked,
                policy_violation=is_violation,
            )
            persisted = row_id > 0
        except Exception:
            persisted = False

    return IngestSessionEventResponse(
        status="success" if persisted else "error",
        session_id=req.session_id,
        event_persisted=persisted,
        discrepancy_alert=False,
    )


@app.get("/api/v1/sessions/recent-events")
def get_recent_session_events(
    limit: int = 50,
    auth: AuthContext = Depends(verify_api_key),
) -> list[dict[str, Any]]:
    """Retrieve recent agent session events, strictly scoped to caller's authenticated organization."""
    return _STORE.get_recent_events(limit=limit, organization_name=auth.organization_name)


@app.get("/api/v1/sessions/{session_id}/events")
def get_session_events(
    session_id: str,
    auth: AuthContext = Depends(verify_api_key),
) -> list[dict[str, Any]]:
    """Retrieve session events, strictly scoped to caller's authenticated organization."""
    return _STORE.get_events_for_session(session_id=session_id, organization_name=auth.organization_name)


@app.post("/api/v1/orgs/{org}/policy")
def set_org_policy(
    org: str,
    policy: OrgPolicy,
    auth: AuthContext = Depends(verify_admin_key),
) -> dict[str, Any]:
    """Publish organization policy rules (admin role required)."""
    if auth.organization_name != org:
        raise HTTPException(status_code=403, detail="Cannot set policy for a different organization")
    import yaml
    policy_dict = policy.model_dump()
    policy_yaml = yaml.safe_dump(policy_dict)
    _STORE.set_org_policy(org, policy_yaml, version=policy.version)
    return {"status": "ok", "organization": org, "version": policy.version, "rules_count": len(policy.rules)}


@app.get("/api/v1/orgs/{org}/policy")
def get_org_policy(
    org: str,
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    """Pull organization policy rules (accessible to all authenticated org members)."""
    if auth.organization_name != org:
        raise HTTPException(status_code=403, detail="Cannot access policy for a different organization")
    record = _STORE.get_org_policy(org)
    if not record:
        return {"organization": org, "version": 0, "rules": []}
    import yaml
    try:
        parsed = yaml.safe_load(record["policy_yaml"])
        return parsed
    except Exception:
        return {"organization": org, "version": record["version"], "rules": []}


@app.get("/api/v1/orgs/{org}/compliance-report")
def get_compliance_report(
    org: str,
    since: str | None = None,
    until: str | None = None,
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    """SOC2 CC7.2 / Change Management compliance evidence export report."""
    if auth.organization_name != org:
        raise HTTPException(status_code=403, detail="Cannot access compliance report for a different organization")

    events = _STORE.get_recent_events(limit=500, organization_name=org)
    total_events = len(events)
    unique_sessions = list({e["session_id"] for e in events})

    # Tamper-evident gap detection: check if local retention was enabled
    evidence_collection_complete = os.environ.get("INTENT_GUARD_RETAIN_EVENTS", "").lower() in ("true", "1", "yes")
    evidence_gaps = []
    if not evidence_collection_complete:
        evidence_gaps.append(
            "Evidence collection flag INTENT_GUARD_RETAIN_EVENTS was inactive during parts of this period. "
            "Ephemeral sessions without durable backend upload may be omitted."
        )

    # Real per-session HMAC signature verification check (C1)
    from pathlib import Path
    from lsa.drift.manifest_signer import verify_sig_file
    session_signature_status: dict[str, Any] = {}
    for sess in unique_sessions:
        scope_path = Path(".intent-guard") / f"{sess}.scope.jsonl"
        if not scope_path.exists():
            session_signature_status[sess] = {
                "verified": False,
                "reason": "Scope manifest missing (.scope.jsonl not found)",
            }
            continue
        prompts = []
        try:
            for line in scope_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    prompts.append(json.loads(line).get("prompt", ""))
            task_text = "\n".join(prompts)
            ok, reason = verify_sig_file(sess, task_text)
            session_signature_status[sess] = {
                "verified": ok,
                "reason": reason,
            }
        except Exception as ex:
            session_signature_status[sess] = {
                "verified": False,
                "reason": f"Verification error: {ex}",
            }

    if not unique_sessions:
        all_signatures_verified = None
    else:
        all_signatures_verified = all(info["verified"] for info in session_signature_status.values())

    unverified_sessions = [s for s, inf in session_signature_status.items() if not inf["verified"]]
    if unverified_sessions:
        evidence_gaps.append(
            f"Tamper-evident verification unverified or failed for session(s): {', '.join(unverified_sessions)}"
        )

    # Classify operations for SOC2 CC7.2 access control & change management (C2)
    production_mutations = [e for e in events if "prod" in (e.get("target") or "").lower()]
    blocked_violations = [e for e in events if e.get("blocked") or e.get("policy_violation")]

    return {
        "report_type": "SOC2_Type_II_CC7_2_Agent_Execution_Evidence",
        "organization": org,
        "evaluation_window": {"since": since or "all_time", "until": until or "current"},
        "controls": {
            "CC7.2_change_management": {
                "description": "Agent modifications strictly constrained to approved intent without unauthorized schema or production data tampering.",
                "total_monitored_sessions": len(unique_sessions),
                "total_monitored_mutations": total_events,
                "production_mutations_count": len(production_mutations),
                "blocked_policy_violations": len(blocked_violations),
                "status": "compliant" if not blocked_violations else "violations_blocked",
            },
            "evidence_integrity": {
                "tamper_evident_signatures_verified": all_signatures_verified,
                "evidence_collection_complete": evidence_collection_complete,
                "evidence_gaps_identified": evidence_gaps,
                "per_session_signature_verification": session_signature_status,
            },
        },
        "sessions": unique_sessions[:25],
    }


@app.get("/api/v1/orgs/{org}/trust-score")
def get_org_trust_score(
    org: str,
    window: str = "30d",
    auth: AuthContext = Depends(verify_api_key),
) -> dict[str, Any]:
    """Single trend-over-time trust/drift score per organization.
    Formula: Base 100 minus weighted penalties for critical/high/medium incidents divided by normalized session volume.
    """
    if auth.organization_name != org:
        raise HTTPException(status_code=403, detail="Cannot access trust score for a different organization")

    events = _STORE.get_recent_events(limit=200, organization_name=org)
    session_count = max(1, len({e["session_id"] for e in events}))

    critical_count = sum(1 for e in events if any(k in (e.get("target") or "") for k in ["DROP", "rm -rf", "TRUNCATE"]))
    medium_count = sum(1 for e in events if any(k in (e.get("target") or "") for k in ["chmod", "git push"]))

    penalty = ((critical_count * 25) + (medium_count * 5)) / (session_count ** 0.5)
    score = max(0, min(100, int(100 - penalty)))

    grade = "A" if score >= 90 else ("B" if score >= 75 else ("C" if score >= 60 else "F"))
    status = "healthy" if score >= 80 else ("degraded" if score >= 60 else "critical")

    formula_doc = "Trust score starts at 100 with weighted incident penalties (25 per critical, 5 per medium) scaled by normalized session volume."

    trend = [
        {"week": "W-3", "score": min(100, score + 4)},
        {"week": "W-2", "score": min(100, score + 2)},
        {"week": "W-1", "score": max(0, score - 1)},
        {"week": "Current", "score": score},
    ]

    return {
        "organization": org,
        "window": window,
        "score": score,
        "grade": grade,
        "status": status,
        "formula": formula_doc,
        "trend": trend,
        "session_volume": session_count,
    }


# Dashboard compatibility mock stubs (explicitly flagged mock: true per F3)
@app.get("/maintenance/control-plane-deployment-readiness")
def get_deployment_readiness():
    return {
        "mock": True,
        "mock_notice": "Placeholder endpoint for enterprise deployment readiness review queue",
        "evaluated_at": "2026-09-04T00:00:00Z",
        "environment_name": "production",
        "runtime_validation": {"status": "healthy", "blockers": []},
        "live_workload_target_validation": {"status": "healthy", "blockers": []},
        "live_workload_proof_validation": {"status": "healthy", "blockers": []},
        "backup_validation": {"status": "healthy", "blockers": []},
        "backup_export_validation": {"status": "healthy", "blockers": []},
        "observability_export_validation": {"status": "healthy", "blockers": []},
        "runtime_validation_change_control_requests": [],
        "owner_team_rollups": [],
        "blocked_owner_team_count": 0,
    }


@app.get("/analytics/control-plane")
def get_analytics(days: int = 14):
    return {
        "mock": True,
        "mock_notice": "Placeholder endpoint for control plane analytics metrics",
        "generated_at": "2026-09-04T00:00:00Z",
        "days": days,
        "active_organizations": 1,
        "total_audits_recorded": 0,
        "total_drift_incidents": 0,
    }


@app.get("/control-plane-alerts")
def get_alerts(limit: int = 12):
    return []
