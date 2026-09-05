from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class IngestSessionEventRequest(BaseModel):
    session_id: str
    tool_name: str
    target: str | None = None
    tool_input: dict[str, Any] = Field(default_factory=dict)
    tool_response: Any = None
    agent_source: str = "claude_code"
    organization_name: str = "default"
    blocked: bool = False
    policy_violation: bool = False


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
    # G1: Gated by verify_api_key and verify_admin_key across routes with organization scoping
    authz_enabled: bool = True
    database_backend: str = "sqlite"  # Local persistent SQLite store (lsa/storage/sqlite_store.py)
    database_ready: bool = False  # Verified dynamically at runtime
    # G1: worker_running is intentionally False because no standalone background worker daemon process exists yet
    worker_running: bool = False


class PolicyMatch(BaseModel):
    target_pattern: str | None = None
    command_pattern: str | None = None
    operation: list[str] | str | None = None


class PolicyRule(BaseModel):
    id: str
    description: str = ""
    match: PolicyMatch
    action: str = "block"  # block | warn | require_approval
    severity: str = "critical"  # critical | high | medium | low


class OrgPolicy(BaseModel):
    organization: str
    version: int = 1
    rules: list[PolicyRule] = Field(default_factory=list)


class EvaluateIncidentRequest(BaseModel):
    task_text: str
    command: str
    tool_name: str = "Bash"


class EvaluateIncidentResponse(BaseModel):
    caught: bool
    status: str
    severity: str
    category: str
    reason: str
    fingerprint: dict[str, Any] = Field(default_factory=dict)
    invariants_checked: list[str] = Field(default_factory=list)
