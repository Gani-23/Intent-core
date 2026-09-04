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

from lsa.storage.sqlite_store import SQLiteEventStore

_STORE = SQLiteEventStore()

# Seed default development/testing API key if configured
_DEFAULT_KEY = os.environ.get("LSA_API_KEY", "lsa-test-key-12345")
if _DEFAULT_KEY:
    _STORE.create_api_key(organization_name="default", raw_key=_DEFAULT_KEY)


class AuthContext:
    def __init__(self, key: str, organization_name: str):
        self.key = key
        self.organization_name = organization_name


def verify_api_key(x_api_key: str | None = Header(None)) -> AuthContext:
    """Validate API Key auth strictly against persistent store."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    key_info = _STORE.lookup_key(x_api_key)
    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if key_info.get("revoked", False):
        raise HTTPException(status_code=401, detail="API key has been revoked")
    return AuthContext(key=x_api_key, organization_name=key_info["organization_name"])


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
        "tool_input": req.tool_input,
        "tool_response": req.tool_response,
    }
    redacted_payload = redact_json_obj(payload)
    event = adapter.parse_event(redacted_payload)

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


@app.get("/api/v1/sessions/{session_id}/events")
def get_session_events(
    session_id: str,
    auth: AuthContext = Depends(verify_api_key),
) -> list[dict[str, Any]]:
    """Retrieve session events, strictly scoped to caller's authenticated organization."""
    return _STORE.get_events_for_session(session_id=session_id, organization_name=auth.organization_name)


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
