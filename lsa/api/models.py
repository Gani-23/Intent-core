from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class IngestSessionEventRequest(BaseModel):
    session_id: str
    tool_name: str
    tool_input: dict[str, Any] = Field(default_factory=dict)
    tool_response: Any = None
    agent_source: str = "claude_code"
    organization_name: str = "default"


class IngestSessionEventResponse(BaseModel):
    status: str
    session_id: str
    event_persisted: bool
    discrepancy_alert: bool = False


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "living-systems-auditor"
    environment_name: str = "production"
    organization_name: str | None = "default"
    auth_required: bool = True
    authz_enabled: bool = True
    database_backend: str = "postgres"
    database_ready: bool = True
    worker_running: bool = True
