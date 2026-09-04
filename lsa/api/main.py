from __future__ import annotations

import os
from typing import Any
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware

from lsa.api.models import (
    HealthResponse,
    IngestSessionEventRequest,
    IngestSessionEventResponse,
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

_VALID_API_KEYS = set(filter(None, os.environ.get("LSA_API_KEYS", "lsa-test-key-12345").split(",")))


def verify_api_key(x_api_key: str | None = Header(None)) -> str:
    """Validate API Key auth."""
    if not x_api_key or x_api_key not in _VALID_API_KEYS:
        # If no key set in environment, allow dev/local access
        if not _VALID_API_KEYS:
            return "dev"
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")
    return x_api_key


@app.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Health check endpoint matching dashboard contract."""
    return HealthResponse()


@app.post("/api/v1/sessions/events", response_model=IngestSessionEventResponse)
def ingest_session_event(
    req: IngestSessionEventRequest,
    _auth: str = Depends(verify_api_key),
) -> IngestSessionEventResponse:
    """Ingest live agent events from Claude Code, Cursor, or Webhooks."""
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
        "tool_input": req.tool_input,
        "tool_response": req.tool_response,
    }
    redacted_payload = redact_json_obj(payload)
    event = adapter.parse_event(redacted_payload)

    return IngestSessionEventResponse(
        status="success",
        session_id=req.session_id,
        event_persisted=bool(event is not None),
        discrepancy_alert=False,
    )


# Dashboard compatibility mock stubs
@app.get("/maintenance/control-plane-deployment-readiness")
def get_deployment_readiness():
    return {
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
        "generated_at": "2026-09-04T00:00:00Z",
        "days": days,
        "active_organizations": 1,
        "total_audits_recorded": 120,
        "total_drift_incidents": 2,
    }


@app.get("/control-plane-alerts")
def get_alerts(limit: int = 12):
    return []
