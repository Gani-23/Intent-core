from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _scope_text(value: Any, *, default: str | None = None) -> str | None:
    text = _optional_text(value)
    if text is None:
        return default
    return text.lower()


def _list_text(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _scope_text(value)
        if text and text not in seen:
            seen.add(text)
            normalized.append(text)
    return normalized


@dataclass(slots=True)
class OrganizationTeamRecord:
    organization_name: str
    team_name: str
    description: str | None = None
    manager_usernames: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)


@dataclass(slots=True)
class OrganizationProjectRecord:
    organization_name: str
    team_name: str | None
    project_name: str
    description: str | None = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)


@dataclass(slots=True)
class OrganizationMembershipRecord:
    username: str
    organization_name: str
    team_name: str | None
    project_name: str | None
    role: str
    status: str = "active"
    granted_by: str | None = None
    granted_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    note: str | None = None


@dataclass(slots=True)
class OrganizationRemovalEventRecord:
    event_id: str
    username: str
    organization_name: str
    team_name: str | None
    project_name: str | None
    role: str
    removed_by: str
    removed_at: str
    reason: str
    prior_status: str = "active"


@dataclass(slots=True)
class OrganizationAssignmentRecord:
    assignment_id: str
    organization_name: str
    team_name: str | None
    project_name: str | None
    work_type: str
    title: str
    subject_id: str | None = None
    assigned_to: str | None = None
    assigned_by: str | None = None
    status: str = "open"
    details: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)


@dataclass(slots=True)
class OrganizationAssignmentCommentRecord:
    comment_id: str
    assignment_id: str
    organization_name: str
    team_name: str | None
    project_name: str | None
    author: str
    body: str
    kind: str = "comment"
    created_at: str = field(default_factory=_now_iso)


@dataclass(slots=True)
class OrganizationWorkspaceSnapshot:
    organization_name: str
    teams: list[OrganizationTeamRecord]
    projects: list[OrganizationProjectRecord]
    memberships: list[OrganizationMembershipRecord]
    removal_events: list[OrganizationRemovalEventRecord]
    assignments: list[OrganizationAssignmentRecord]
    assignment_comments: list[OrganizationAssignmentCommentRecord]


@dataclass(slots=True)
class OrganizationDirectoryService:
    path: Path
    default_organization_name: str

    def snapshot(self, organization_name: str | None = None) -> OrganizationWorkspaceSnapshot:
        effective_org = _scope_text(organization_name, default=self.default_organization_name) or self.default_organization_name
        payload = self._read_payload()
        teams = [
            OrganizationTeamRecord(**record)
            for record in payload.get("teams", [])
            if _scope_text(record.get("organization_name"), default=self.default_organization_name) == effective_org
        ]
        projects = [
            OrganizationProjectRecord(**record)
            for record in payload.get("projects", [])
            if _scope_text(record.get("organization_name"), default=self.default_organization_name) == effective_org
        ]
        memberships = [
            OrganizationMembershipRecord(**record)
            for record in payload.get("memberships", [])
            if _scope_text(record.get("organization_name"), default=self.default_organization_name) == effective_org
        ]
        removals = [
            OrganizationRemovalEventRecord(**record)
            for record in payload.get("removal_events", [])
            if _scope_text(record.get("organization_name"), default=self.default_organization_name) == effective_org
        ]
        assignments = [
            OrganizationAssignmentRecord(**record)
            for record in payload.get("assignments", [])
            if _scope_text(record.get("organization_name"), default=self.default_organization_name) == effective_org
        ]
        comments = [
            OrganizationAssignmentCommentRecord(**record)
            for record in payload.get("assignment_comments", [])
            if _scope_text(record.get("organization_name"), default=self.default_organization_name) == effective_org
        ]
        return OrganizationWorkspaceSnapshot(
            organization_name=effective_org,
            teams=sorted(teams, key=lambda item: item.team_name),
            projects=sorted(projects, key=lambda item: (item.team_name or "", item.project_name)),
            memberships=sorted(memberships, key=lambda item: (item.username, item.team_name or "", item.project_name or "")),
            removal_events=sorted(removals, key=lambda item: item.removed_at, reverse=True),
            assignments=sorted(assignments, key=lambda item: item.updated_at, reverse=True),
            assignment_comments=sorted(comments, key=lambda item: item.created_at, reverse=True),
        )

    def resolve_primary_membership(
        self,
        username: str,
        organization_name: str | None = None,
    ) -> OrganizationMembershipRecord | None:
        normalized_username = _scope_text(username)
        if not normalized_username:
            return None
        snapshot = self.snapshot(organization_name)
        active = [
          membership
          for membership in snapshot.memberships
          if membership.username == normalized_username and membership.status == "active"
        ]
        if not active:
            return None
        return sorted(
            active,
            key=lambda item: (
                0 if item.project_name else 1,
                0 if item.team_name else 1,
                item.updated_at,
            ),
            reverse=True,
        )[0]

    def user_has_management_access(self, username: str, organization_name: str | None = None) -> bool:
        membership = self.resolve_primary_membership(username, organization_name)
        if membership is None or membership.status != "active":
            return False
        return membership.role in {"org_owner", "org_admin", "manager"}

    def upsert_team(
        self,
        *,
        organization_name: str | None,
        team_name: str,
        description: str | None,
        manager_usernames: list[str],
    ) -> OrganizationTeamRecord:
        organization = _scope_text(organization_name, default=self.default_organization_name) or self.default_organization_name
        team = _scope_text(team_name)
        if not team:
            raise ValueError("Team name is required.")
        payload = self._read_payload()
        now = _now_iso()
        teams = payload.setdefault("teams", [])
        record = next(
            (item for item in teams if _scope_text(item.get("organization_name"), default=self.default_organization_name) == organization and _scope_text(item.get("team_name")) == team),
            None,
        )
        if record is None:
            record = {
                "organization_name": organization,
                "team_name": team,
                "description": _optional_text(description),
                "manager_usernames": _list_text(manager_usernames),
                "created_at": now,
                "updated_at": now,
            }
            teams.append(record)
        else:
            record["description"] = _optional_text(description)
            record["manager_usernames"] = _list_text(manager_usernames)
            record["updated_at"] = now
        self._write_payload(payload)
        return OrganizationTeamRecord(**record)

    def upsert_project(
        self,
        *,
        organization_name: str | None,
        team_name: str | None,
        project_name: str,
        description: str | None,
    ) -> OrganizationProjectRecord:
        organization = _scope_text(organization_name, default=self.default_organization_name) or self.default_organization_name
        project = _scope_text(project_name)
        team = _scope_text(team_name)
        if not project:
            raise ValueError("Project name is required.")
        payload = self._read_payload()
        now = _now_iso()
        projects = payload.setdefault("projects", [])
        record = next(
            (
                item
                for item in projects
                if _scope_text(item.get("organization_name"), default=self.default_organization_name) == organization
                and _scope_text(item.get("team_name")) == team
                and _scope_text(item.get("project_name")) == project
            ),
            None,
        )
        if record is None:
            record = {
                "organization_name": organization,
                "team_name": team,
                "project_name": project,
                "description": _optional_text(description),
                "created_at": now,
                "updated_at": now,
            }
            projects.append(record)
        else:
            record["description"] = _optional_text(description)
            record["updated_at"] = now
        self._write_payload(payload)
        return OrganizationProjectRecord(**record)

    def upsert_membership(
        self,
        *,
        username: str,
        organization_name: str | None,
        team_name: str | None,
        project_name: str | None,
        role: str,
        granted_by: str | None,
        note: str | None,
    ) -> OrganizationMembershipRecord:
        normalized_username = _scope_text(username)
        organization = _scope_text(organization_name, default=self.default_organization_name) or self.default_organization_name
        team = _scope_text(team_name)
        project = _scope_text(project_name)
        normalized_role = _scope_text(role)
        if not normalized_username:
            raise ValueError("Username is required.")
        if not normalized_role:
            raise ValueError("Membership role is required.")
        payload = self._read_payload()
        now = _now_iso()
        memberships = payload.setdefault("memberships", [])
        record = next(
            (
                item
                for item in memberships
                if _scope_text(item.get("username")) == normalized_username
                and _scope_text(item.get("organization_name"), default=self.default_organization_name) == organization
                and _scope_text(item.get("team_name")) == team
                and _scope_text(item.get("project_name")) == project
            ),
            None,
        )
        if record is None:
            record = {
                "username": normalized_username,
                "organization_name": organization,
                "team_name": team,
                "project_name": project,
                "role": normalized_role,
                "status": "active",
                "granted_by": _optional_text(granted_by),
                "granted_at": now,
                "updated_at": now,
                "note": _optional_text(note),
            }
            memberships.append(record)
        else:
            record["role"] = normalized_role
            record["status"] = "active"
            record["granted_by"] = _optional_text(granted_by) or record.get("granted_by")
            record["updated_at"] = now
            record["note"] = _optional_text(note)
        self._write_payload(payload)
        return OrganizationMembershipRecord(**record)

    def remove_membership(
        self,
        *,
        username: str,
        organization_name: str | None,
        team_name: str | None,
        project_name: str | None,
        removed_by: str,
        reason: str,
    ) -> OrganizationRemovalEventRecord:
        normalized_username = _scope_text(username)
        organization = _scope_text(organization_name, default=self.default_organization_name) or self.default_organization_name
        team = _scope_text(team_name)
        project = _scope_text(project_name)
        if not normalized_username:
            raise ValueError("Username is required.")
        if not _optional_text(reason):
            raise ValueError("Removal reason is required.")
        payload = self._read_payload()
        memberships = payload.setdefault("memberships", [])
        record = next(
            (
                item
                for item in memberships
                if _scope_text(item.get("username")) == normalized_username
                and _scope_text(item.get("organization_name"), default=self.default_organization_name) == organization
                and _scope_text(item.get("team_name")) == team
                and _scope_text(item.get("project_name")) == project
                and _scope_text(item.get("status"), default="active") == "active"
            ),
            None,
        )
        if record is None:
            raise ValueError("Active membership not found for removal.")
        removed_at = _now_iso()
        prior_role = _scope_text(record.get("role")) or "viewer"
        prior_status = _scope_text(record.get("status"), default="active") or "active"
        record["status"] = "removed"
        record["updated_at"] = removed_at
        record["note"] = _optional_text(reason)
        event = {
            "event_id": uuid4().hex[:16],
            "username": normalized_username,
            "organization_name": organization,
            "team_name": team,
            "project_name": project,
            "role": prior_role,
            "removed_by": _scope_text(removed_by) or "admin",
            "removed_at": removed_at,
            "reason": _text(reason),
            "prior_status": prior_status,
        }
        payload.setdefault("removal_events", []).append(event)
        self._write_payload(payload)
        return OrganizationRemovalEventRecord(**event)

    def create_assignment(
        self,
        *,
        organization_name: str | None,
        team_name: str | None,
        project_name: str | None,
        work_type: str,
        title: str,
        subject_id: str | None,
        assigned_to: str | None,
        assigned_by: str | None,
        details: dict[str, Any] | None,
    ) -> OrganizationAssignmentRecord:
        organization = _scope_text(organization_name, default=self.default_organization_name) or self.default_organization_name
        team = _scope_text(team_name)
        project = _scope_text(project_name)
        normalized_type = _scope_text(work_type)
        normalized_title = _optional_text(title)
        if not normalized_type:
            raise ValueError("Assignment work type is required.")
        if not normalized_title:
            raise ValueError("Assignment title is required.")
        now = _now_iso()
        record = {
            "assignment_id": uuid4().hex[:16],
            "organization_name": organization,
            "team_name": team,
            "project_name": project,
            "work_type": normalized_type,
            "title": normalized_title,
            "subject_id": _optional_text(subject_id),
            "assigned_to": _scope_text(assigned_to),
            "assigned_by": _scope_text(assigned_by),
            "status": "open",
            "details": details or {},
            "created_at": now,
            "updated_at": now,
        }
        payload = self._read_payload()
        payload.setdefault("assignments", []).append(record)
        self._write_payload(payload)
        return OrganizationAssignmentRecord(**record)

    def update_assignment(
        self,
        *,
        assignment_id: str,
        changed_by: str,
        status: str | None = None,
        assigned_to: str | None = None,
        title: str | None = None,
        details: dict[str, Any] | None = None,
        comment: str | None = None,
    ) -> OrganizationAssignmentRecord:
        normalized_assignment_id = _scope_text(assignment_id)
        if not normalized_assignment_id:
            raise ValueError("Assignment id is required.")
        payload = self._read_payload()
        assignments = payload.setdefault("assignments", [])
        record = next((item for item in assignments if _scope_text(item.get("assignment_id")) == normalized_assignment_id), None)
        if record is None:
            raise ValueError("Assignment not found.")
        now = _now_iso()
        if _optional_text(status):
            record["status"] = _scope_text(status)
        if assigned_to is not None:
            record["assigned_to"] = _scope_text(assigned_to)
        if title is not None and _optional_text(title):
            record["title"] = _optional_text(title)
        if details is not None:
            record["details"] = details
        record["updated_at"] = now
        if _optional_text(comment):
            payload.setdefault("assignment_comments", []).append(
                {
                    "comment_id": uuid4().hex[:16],
                    "assignment_id": normalized_assignment_id,
                    "organization_name": record.get("organization_name") or self.default_organization_name,
                    "team_name": record.get("team_name"),
                    "project_name": record.get("project_name"),
                    "author": _scope_text(changed_by) or "system",
                    "body": _text(comment),
                    "kind": "status_change" if _optional_text(status) else "comment",
                    "created_at": now,
                }
            )
        self._write_payload(payload)
        return OrganizationAssignmentRecord(**record)

    def add_assignment_comment(
        self,
        *,
        assignment_id: str,
        author: str,
        body: str,
    ) -> OrganizationAssignmentCommentRecord:
        normalized_assignment_id = _scope_text(assignment_id)
        normalized_author = _scope_text(author)
        if not normalized_assignment_id:
            raise ValueError("Assignment id is required.")
        if not normalized_author:
            raise ValueError("Comment author is required.")
        if not _optional_text(body):
            raise ValueError("Comment body is required.")
        payload = self._read_payload()
        assignments = payload.setdefault("assignments", [])
        record = next((item for item in assignments if _scope_text(item.get("assignment_id")) == normalized_assignment_id), None)
        if record is None:
            raise ValueError("Assignment not found.")
        comment = {
            "comment_id": uuid4().hex[:16],
            "assignment_id": normalized_assignment_id,
            "organization_name": record.get("organization_name") or self.default_organization_name,
            "team_name": record.get("team_name"),
            "project_name": record.get("project_name"),
            "author": normalized_author,
            "body": _text(body),
            "kind": "comment",
            "created_at": _now_iso(),
        }
        payload.setdefault("assignment_comments", []).append(comment)
        record["updated_at"] = comment["created_at"]
        self._write_payload(payload)
        return OrganizationAssignmentCommentRecord(**comment)

    def _read_payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default_payload()
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return self._default_payload()

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _default_payload(self) -> dict[str, Any]:
        return {
            "teams": [],
            "projects": [],
            "memberships": [],
            "removal_events": [],
            "assignments": [],
            "assignment_comments": [],
        }
