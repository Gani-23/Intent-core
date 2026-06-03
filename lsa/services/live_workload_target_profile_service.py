from __future__ import annotations

import json
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Callable


def _optional_text(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    text = str(value).strip()
    return text or None


def _optional_headers(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    normalized: dict[str, str] = {}
    for key, raw_value in value.items():
        header_name = _optional_text(key)
        header_value = _optional_text(raw_value)
        if header_name and header_value is not None:
            normalized[header_name] = header_value
    return normalized or None


def _optional_status_codes(value: Any) -> list[int] | None:
    if value is None or value == "":
        return None
    if not isinstance(value, list):
        return None
    normalized: list[int] = []
    for item in value:
        try:
            code = int(item)
        except (TypeError, ValueError):
            continue
        if 100 <= code <= 599:
            normalized.append(code)
    return normalized or None


def _normalize_method(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    normalized = text.upper()
    if normalized not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
        raise ValueError(f"Unsupported HTTP method: {text}")
    return normalized


def _optional_scope_text(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    return text.lower()


def resolve_target_headers(
    headers: dict[str, str] | None,
    *,
    secret_lookup: Callable[[str], str | None] | None = None,
) -> tuple[dict[str, str], list[str]]:
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for key, raw_value in (headers or {}).items():
        if raw_value.startswith("env:"):
            env_name = raw_value[4:].strip()
            env_value = os.getenv(env_name)
            if env_value is None:
                missing.append(env_name)
                continue
            resolved[key] = env_value
            continue
        if raw_value.startswith("secret:"):
            alias = raw_value[7:].strip()
            secret_value = secret_lookup(alias) if secret_lookup is not None else None
            if secret_value is None:
                missing.append(f"secret:{alias}")
                continue
            resolved[key] = secret_value
            continue
        resolved[key] = raw_value
    return resolved, missing


@dataclass(slots=True)
class LiveWorkloadTargetProfile:
    name: str
    approved_base_url: str
    drift_base_url: str
    source: str
    organization_name: str | None = None
    team_name: str | None = None
    project_name: str | None = None
    environment_name: str | None = None
    approved_probe_url: str | None = None
    drift_probe_url: str | None = None
    approved_action_url: str | None = None
    drift_action_url: str | None = None
    approved_probe_method: str | None = None
    drift_probe_method: str | None = None
    approved_action_method: str | None = None
    drift_action_method: str | None = None
    approved_headers: dict[str, str] | None = None
    drift_headers: dict[str, str] | None = None
    approved_expected_statuses: list[int] | None = None
    drift_expected_statuses: list[int] | None = None
    request_timeout_seconds: float | None = None
    built_in: bool = False
    enabled: bool = True
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "approved_target_base_url": self.approved_base_url,
            "drift_target_base_url": self.drift_base_url,
            "organization_name": self.organization_name,
            "team_name": self.team_name,
            "project_name": self.project_name,
            "environment_name": self.environment_name,
            "approved_probe_url": self.approved_probe_url,
            "drift_probe_url": self.drift_probe_url,
            "approved_action_url": self.approved_action_url,
            "drift_action_url": self.drift_action_url,
            "approved_probe_method": self.approved_probe_method,
            "drift_probe_method": self.drift_probe_method,
            "approved_action_method": self.approved_action_method,
            "drift_action_method": self.drift_action_method,
            "approved_headers": self.approved_headers,
            "drift_headers": self.drift_headers,
            "approved_expected_statuses": self.approved_expected_statuses,
            "drift_expected_statuses": self.drift_expected_statuses,
            "request_timeout_seconds": self.request_timeout_seconds,
            "source": self.source,
            "built_in": self.built_in,
            "enabled": self.enabled,
            "description": self.description,
        }


@dataclass(slots=True)
class LiveWorkloadTargetProfileService:
    settings: Any

    def _default_organization_name(self) -> str:
        return _optional_scope_text(getattr(self.settings, "organization_name", None)) or "default"

    def _default_environment_name(self) -> str:
        return _optional_scope_text(getattr(self.settings, "environment_name", None)) or "default"

    def list_profiles(self) -> list[LiveWorkloadTargetProfile]:
        profiles: dict[str, LiveWorkloadTargetProfile] = {
            profile.name: profile for profile in self._built_in_profiles()
        }
        for profile in self._file_profiles():
            profiles[profile.name] = profile
        return sorted(profiles.values(), key=lambda item: (not item.built_in, item.name))

    def resolve(self, name: str | None) -> LiveWorkloadTargetProfile | None:
        normalized = (name or "").strip().lower()
        if not normalized:
            return None
        for profile in self.list_profiles():
            if profile.name == normalized and profile.enabled:
                return profile
        return None

    def upsert_profile(
        self,
        *,
        name: str,
        approved_base_url: str,
        drift_base_url: str,
        organization_name: str | None = None,
        team_name: str | None = None,
        project_name: str | None = None,
        environment_name: str | None = None,
        approved_probe_url: str | None = None,
        drift_probe_url: str | None = None,
        approved_action_url: str | None = None,
        drift_action_url: str | None = None,
        approved_probe_method: str | None = None,
        drift_probe_method: str | None = None,
        approved_action_method: str | None = None,
        drift_action_method: str | None = None,
        approved_headers: dict[str, str] | None = None,
        drift_headers: dict[str, str] | None = None,
        approved_expected_statuses: list[int] | None = None,
        drift_expected_statuses: list[int] | None = None,
        request_timeout_seconds: float | None = None,
        enabled: bool = True,
        description: str | None = None,
    ) -> LiveWorkloadTargetProfile:
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("Profile name is required.")
        if any(profile.name == normalized for profile in self._built_in_profiles()):
            raise ValueError("Built-in target profiles cannot be modified.")
        approved = approved_base_url.strip().rstrip("/")
        drift = drift_base_url.strip().rstrip("/")
        approved_probe = approved_probe_url.strip() if approved_probe_url else None
        drift_probe = drift_probe_url.strip() if drift_probe_url else None
        approved_action = approved_action_url.strip() if approved_action_url else None
        drift_action = drift_action_url.strip() if drift_action_url else None
        probe_method = _normalize_method(approved_probe_method)
        drift_probe_http_method = _normalize_method(drift_probe_method)
        action_method = _normalize_method(approved_action_method)
        drift_action_http_method = _normalize_method(drift_action_method)
        approved_header_map = _optional_headers(approved_headers)
        drift_header_map = _optional_headers(drift_headers)
        approved_statuses = _optional_status_codes(approved_expected_statuses)
        drift_statuses = _optional_status_codes(drift_expected_statuses)
        timeout_value = float(request_timeout_seconds) if request_timeout_seconds is not None else None
        if timeout_value is not None and timeout_value <= 0:
            raise ValueError("Request timeout seconds must be greater than zero.")
        if not approved or not drift:
            raise ValueError("Both approved and drift target base URLs are required.")
        organization = _optional_scope_text(organization_name) or self._default_organization_name()
        team = _optional_scope_text(team_name)
        project = _optional_scope_text(project_name)
        environment = _optional_scope_text(environment_name) or self._default_environment_name()
        profiles = self._read_file_profile_entries()
        profiles[normalized] = {
            "name": normalized,
            "approved_target_base_url": approved,
            "drift_target_base_url": drift,
            "organization_name": organization,
            "team_name": team,
            "project_name": project,
            "environment_name": environment,
            "approved_probe_url": approved_probe or None,
            "drift_probe_url": drift_probe or None,
            "approved_action_url": approved_action or None,
            "drift_action_url": drift_action or None,
            "approved_probe_method": probe_method,
            "drift_probe_method": drift_probe_http_method,
            "approved_action_method": action_method,
            "drift_action_method": drift_action_http_method,
            "approved_headers": approved_header_map,
            "drift_headers": drift_header_map,
            "approved_expected_statuses": approved_statuses,
            "drift_expected_statuses": drift_statuses,
            "request_timeout_seconds": timeout_value,
            "enabled": bool(enabled),
            "description": None if description in {None, ""} else str(description),
        }
        self._write_file_profile_entries(profiles)
        return LiveWorkloadTargetProfile(
            name=normalized,
            approved_base_url=approved,
            drift_base_url=drift,
            organization_name=organization,
            team_name=team,
            project_name=project,
            environment_name=environment,
            approved_probe_url=approved_probe or None,
            drift_probe_url=drift_probe or None,
            approved_action_url=approved_action or None,
            drift_action_url=drift_action or None,
            approved_probe_method=probe_method,
            drift_probe_method=drift_probe_http_method,
            approved_action_method=action_method,
            drift_action_method=drift_action_http_method,
            approved_headers=approved_header_map,
            drift_headers=drift_header_map,
            approved_expected_statuses=approved_statuses,
            drift_expected_statuses=drift_statuses,
            request_timeout_seconds=timeout_value,
            source=str(self._profile_path()),
            built_in=False,
            enabled=bool(enabled),
            description=None if description in {None, ""} else str(description),
        )

    def delete_profile(self, name: str) -> bool:
        normalized = name.strip().lower()
        if not normalized:
            return False
        if any(profile.name == normalized for profile in self._built_in_profiles()):
            raise ValueError("Built-in target profiles cannot be deleted.")
        profiles = self._read_file_profile_entries()
        existed = normalized in profiles
        if existed:
            profiles.pop(normalized, None)
            self._write_file_profile_entries(profiles)
        return existed

    def _built_in_profiles(self) -> list[LiveWorkloadTargetProfile]:
        return [
            LiveWorkloadTargetProfile(
                name="public-echo-pair",
                approved_base_url="https://httpbingo.org/anything",
                drift_base_url="https://httpbun.com/anything",
                organization_name=self._default_organization_name(),
                environment_name=self._default_environment_name(),
                approved_probe_url="https://httpbingo.org/anything",
                drift_probe_url="https://httpbun.com/anything",
                approved_action_url="https://httpbingo.org/anything",
                drift_action_url="https://httpbun.com/anything",
                approved_probe_method="GET",
                drift_probe_method="GET",
                approved_action_method="GET",
                drift_action_method="GET",
                approved_expected_statuses=[200],
                drift_expected_statuses=[200],
                source="built-in",
                built_in=True,
                description="Public echo pair using httpbingo for approved and httpbun for drift.",
            ),
            LiveWorkloadTargetProfile(
                name="public-failing-pair",
                approved_base_url="https://httpbingo.org/status/503",
                drift_base_url="https://httpbun.com/status/404",
                organization_name=self._default_organization_name(),
                environment_name=self._default_environment_name(),
                approved_probe_url="https://httpbingo.org/status/503",
                drift_probe_url="https://httpbun.com/status/404",
                approved_action_url="https://httpbingo.org/status/503",
                drift_action_url="https://httpbun.com/status/404",
                approved_probe_method="GET",
                drift_probe_method="GET",
                approved_action_method="GET",
                drift_action_method="GET",
                approved_expected_statuses=[200],
                drift_expected_statuses=[200],
                source="built-in",
                built_in=True,
                description="Intentional failing pair for testing validation, incident, and AI explanation flows.",
            ),
            LiveWorkloadTargetProfile(
                name="public-httpbin-bingo-pair",
                approved_base_url="https://httpbin.org/anything",
                drift_base_url="https://httpbingo.org/anything",
                organization_name=self._default_organization_name(),
                environment_name=self._default_environment_name(),
                approved_probe_url="https://httpbin.org/anything",
                drift_probe_url="https://httpbingo.org/anything",
                approved_action_url="https://httpbin.org/anything",
                drift_action_url="https://httpbingo.org/anything",
                approved_probe_method="GET",
                drift_probe_method="GET",
                approved_action_method="GET",
                drift_action_method="GET",
                approved_expected_statuses=[200],
                drift_expected_statuses=[200],
                source="built-in",
                built_in=True,
                description="Public pair using httpbin for approved and httpbingo for drift.",
            ),
        ]

    def _file_profiles(self) -> list[LiveWorkloadTargetProfile]:
        path = self._profile_path()
        if not path or not path.exists():
            return []
        entries = list(self._read_file_profile_entries().values())
        profiles: list[LiveWorkloadTargetProfile] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip().lower()
            approved = str(entry.get("approved_target_base_url", "")).strip().rstrip("/")
            drift = str(entry.get("drift_target_base_url", "")).strip().rstrip("/")
            approved_probe = _optional_text(entry.get("approved_probe_url"))
            drift_probe = _optional_text(entry.get("drift_probe_url"))
            approved_action = _optional_text(entry.get("approved_action_url"))
            drift_action = _optional_text(entry.get("drift_action_url"))
            approved_probe_method = _normalize_method(entry.get("approved_probe_method")) if entry.get("approved_probe_method") else None
            drift_probe_method = _normalize_method(entry.get("drift_probe_method")) if entry.get("drift_probe_method") else None
            approved_action_method = _normalize_method(entry.get("approved_action_method")) if entry.get("approved_action_method") else None
            drift_action_method = _normalize_method(entry.get("drift_action_method")) if entry.get("drift_action_method") else None
            approved_headers = _optional_headers(entry.get("approved_headers"))
            drift_headers = _optional_headers(entry.get("drift_headers"))
            approved_expected_statuses = _optional_status_codes(entry.get("approved_expected_statuses"))
            drift_expected_statuses = _optional_status_codes(entry.get("drift_expected_statuses"))
            timeout_value = entry.get("request_timeout_seconds")
            if not name or not approved or not drift:
                continue
            profiles.append(
                LiveWorkloadTargetProfile(
                    name=name,
                    approved_base_url=approved,
                    drift_base_url=drift,
                    organization_name=_optional_scope_text(entry.get("organization_name")) or self._default_organization_name(),
                    team_name=_optional_scope_text(entry.get("team_name")),
                    project_name=_optional_scope_text(entry.get("project_name")),
                    environment_name=_optional_scope_text(entry.get("environment_name")) or self._default_environment_name(),
                    approved_probe_url=approved_probe,
                    drift_probe_url=drift_probe,
                    approved_action_url=approved_action,
                    drift_action_url=drift_action,
                    approved_probe_method=approved_probe_method,
                    drift_probe_method=drift_probe_method,
                    approved_action_method=approved_action_method,
                    drift_action_method=drift_action_method,
                    approved_headers=approved_headers,
                    drift_headers=drift_headers,
                    approved_expected_statuses=approved_expected_statuses,
                    drift_expected_statuses=drift_expected_statuses,
                    request_timeout_seconds=float(timeout_value) if timeout_value is not None else None,
                    source=str(path),
                    built_in=False,
                    enabled=bool(entry.get("enabled", True)),
                    description=(
                        None
                        if entry.get("description") in {None, ""}
                        else str(entry.get("description"))
                    ),
                )
            )
        return profiles

    def _profile_path(self) -> Path:
        return Path(getattr(self.settings, "workload_target_profiles_path", ""))

    def _read_file_profile_entries(self) -> dict[str, dict[str, Any]]:
        path = self._profile_path()
        if not path or not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        entries = raw.get("profiles", []) if isinstance(raw, dict) else raw
        if not isinstance(entries, list):
            return {}
        normalized_entries: dict[str, dict[str, Any]] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip().lower()
            approved = str(entry.get("approved_target_base_url", "")).strip().rstrip("/")
            drift = str(entry.get("drift_target_base_url", "")).strip().rstrip("/")
            approved_probe = _optional_text(entry.get("approved_probe_url"))
            drift_probe = _optional_text(entry.get("drift_probe_url"))
            approved_action = _optional_text(entry.get("approved_action_url"))
            drift_action = _optional_text(entry.get("drift_action_url"))
            approved_probe_method = _normalize_method(entry.get("approved_probe_method")) if entry.get("approved_probe_method") else None
            drift_probe_method = _normalize_method(entry.get("drift_probe_method")) if entry.get("drift_probe_method") else None
            approved_action_method = _normalize_method(entry.get("approved_action_method")) if entry.get("approved_action_method") else None
            drift_action_method = _normalize_method(entry.get("drift_action_method")) if entry.get("drift_action_method") else None
            approved_headers = _optional_headers(entry.get("approved_headers"))
            drift_headers = _optional_headers(entry.get("drift_headers"))
            approved_expected_statuses = _optional_status_codes(entry.get("approved_expected_statuses"))
            drift_expected_statuses = _optional_status_codes(entry.get("drift_expected_statuses"))
            timeout_value = entry.get("request_timeout_seconds")
            if not name or not approved or not drift:
                continue
            normalized_entries[name] = {
                "name": name,
                "approved_target_base_url": approved,
                "drift_target_base_url": drift,
                "organization_name": _optional_scope_text(entry.get("organization_name")) or self._default_organization_name(),
                "team_name": _optional_scope_text(entry.get("team_name")),
                "project_name": _optional_scope_text(entry.get("project_name")),
                "environment_name": _optional_scope_text(entry.get("environment_name")) or self._default_environment_name(),
                "approved_probe_url": approved_probe,
                "drift_probe_url": drift_probe,
                "approved_action_url": approved_action,
                "drift_action_url": drift_action,
                "approved_probe_method": approved_probe_method,
                "drift_probe_method": drift_probe_method,
                "approved_action_method": approved_action_method,
                "drift_action_method": drift_action_method,
                "approved_headers": approved_headers,
                "drift_headers": drift_headers,
                "approved_expected_statuses": approved_expected_statuses,
                "drift_expected_statuses": drift_expected_statuses,
                "request_timeout_seconds": float(timeout_value) if timeout_value is not None else None,
                "enabled": bool(entry.get("enabled", True)),
                "description": None if entry.get("description") in {None, ""} else str(entry.get("description")),
            }
        return normalized_entries

    def _write_file_profile_entries(self, profiles: dict[str, dict[str, Any]]) -> None:
        path = self._profile_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"profiles": [profiles[name] for name in sorted(profiles)]}
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
