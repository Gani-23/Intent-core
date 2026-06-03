from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import json
import os
import re
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _alias_text(value: Any) -> str:
    return _text(value).lower().replace(" ", "_").replace("-", "_")


_ALIAS_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_ENV_VAR_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _validate_alias_name(alias: str) -> str:
    if not alias:
        raise ValueError("Secret alias is required.")
    if not _ALIAS_PATTERN.fullmatch(alias):
        raise ValueError("Secret alias must use lowercase letters, numbers, and underscores only.")
    return alias


def _validate_env_var_name(env_var_name: str) -> str:
    if not env_var_name:
        raise ValueError("Environment variable name is required.")
    if not _ENV_VAR_PATTERN.fullmatch(env_var_name):
        raise ValueError("Environment variable name must use uppercase letters, numbers, and underscores only.")
    return env_var_name


@dataclass(slots=True)
class SecretAliasRecord:
    alias: str
    env_var_name: str
    description: str | None = None
    usage_scope: str | None = None
    created_at: str = _now_iso()
    updated_at: str = _now_iso()

    def to_public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["present"] = os.getenv(self.env_var_name) is not None
        return payload


@dataclass(slots=True)
class SecretReferenceService:
    path: Path

    def list_aliases(self) -> list[SecretAliasRecord]:
        payload = self._read_payload()
        rows = [SecretAliasRecord(**record) for record in payload.get("aliases", [])]
        return sorted(rows, key=lambda item: item.alias)

    def upsert_alias(
        self,
        *,
        alias: str,
        env_var_name: str,
        description: str | None = None,
        usage_scope: str | None = None,
    ) -> SecretAliasRecord:
        normalized_alias = _alias_text(alias)
        normalized_env = _text(env_var_name).upper().replace("-", "_").replace(" ", "_")
        _validate_alias_name(normalized_alias)
        _validate_env_var_name(normalized_env)
        now = _now_iso()
        payload = self._read_payload()
        entries = payload.setdefault("aliases", [])
        record = next((item for item in entries if _alias_text(item.get("alias")) == normalized_alias), None)
        if record is None:
            record = {
                "alias": normalized_alias,
                "env_var_name": normalized_env,
                "description": _optional_text(description),
                "usage_scope": _optional_text(usage_scope),
                "created_at": now,
                "updated_at": now,
            }
            entries.append(record)
        else:
            record["env_var_name"] = normalized_env
            record["description"] = _optional_text(description)
            record["usage_scope"] = _optional_text(usage_scope)
            record["updated_at"] = now
        self._write_payload(payload)
        return SecretAliasRecord(**record)

    def delete_alias(self, alias: str) -> bool:
        normalized_alias = _alias_text(alias)
        if not normalized_alias:
            return False
        payload = self._read_payload()
        existing = payload.get("aliases", [])
        remaining = [item for item in existing if _alias_text(item.get("alias")) != normalized_alias]
        if len(remaining) == len(existing):
            return False
        payload["aliases"] = remaining
        self._write_payload(payload)
        return True

    def resolve_secret_alias(self, alias: str) -> str | None:
        normalized_alias = _alias_text(alias)
        if not normalized_alias:
            return None
        for record in self.list_aliases():
            if record.alias == normalized_alias:
                return os.getenv(record.env_var_name)
        return None

    def resolve_reference_token(self, value: str) -> str | None:
        raw = _text(value)
        if not raw.startswith("secret:"):
            return None
        return self.resolve_secret_alias(raw[7:])

    def _read_payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"aliases": []}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"aliases": []}

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
