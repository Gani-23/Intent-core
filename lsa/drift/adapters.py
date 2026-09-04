#!/usr/bin/env python3
"""Multi-agent adapter framework for Intent Guard.

Normalizes diverse agent telemetry (Claude Code, Cursor, GitHub Copilot Workspace,
Aider, Windsurf, custom agents) into unified ObservedEvent instances.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from lsa.drift.models import ObservedEvent


class AgentAdapter:
    """Base interface for agent event adapters."""

    def parse_event(self, raw_payload: dict[str, Any]) -> ObservedEvent | None:
        raise NotImplementedError


class ClaudeCodeAdapter(AgentAdapter):
    """Adapter for Claude Code hook payloads."""

    def parse_event(self, raw_payload: dict[str, Any]) -> ObservedEvent | None:
        tool_name = str(raw_payload.get("tool_name", ""))
        tool_input = raw_payload.get("tool_input") or {}
        session_id = str(raw_payload.get("session_id", "default"))
        if tool_name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            target = str(tool_input.get("file_path", tool_input.get("notebook_path", "")))
            return ObservedEvent(
                function=f"session:{session_id}",
                event_type="mutation",
                target=target,
                metadata={"tool_name": tool_name, "source": "claude_code"},
            )
        if tool_name == "Bash":
            cmd = str(tool_input.get("command", ""))
            return ObservedEvent(
                function=f"session:{session_id}",
                event_type="mutation",
                target=cmd,
                metadata={"tool_name": tool_name, "command": cmd, "source": "claude_code"},
            )
        return None


class CursorAgentAdapter(AgentAdapter):
    """Adapter for Cursor Agent / Composer execution events."""

    def parse_event(self, raw_payload: dict[str, Any]) -> ObservedEvent | None:
        # Cursor style payloads: action_type, file_path, command, conversation_id
        session_id = str(raw_payload.get("conversation_id", raw_payload.get("session_id", "cursor-default")))
        action = str(raw_payload.get("action_type", raw_payload.get("type", ""))).lower()
        
        if action in ("edit_file", "create_file", "write_file"):
            target = str(raw_payload.get("file_path", raw_payload.get("path", "")))
            return ObservedEvent(
                function=f"session:{session_id}",
                event_type="mutation",
                target=target,
                metadata={"tool_name": "Edit", "source": "cursor_composer"},
            )
        if action in ("terminal_run", "shell_exec", "run_command"):
            cmd = str(raw_payload.get("command", raw_payload.get("cmd", "")))
            return ObservedEvent(
                function=f"session:{session_id}",
                event_type="mutation",
                target=cmd,
                metadata={"tool_name": "Bash", "command": cmd, "source": "cursor_composer"},
            )
        return None


class GenericWebhookAdapter(AgentAdapter):
    """Universal adapter for custom agents and webhooks."""

    def parse_event(self, raw_payload: dict[str, Any]) -> ObservedEvent | None:
        session_id = str(raw_payload.get("session_id", "generic"))
        target = str(raw_payload.get("target", ""))
        tool_name = str(raw_payload.get("tool_name", raw_payload.get("op", "GenericAction")))
        if not target:
            return None
        return ObservedEvent(
            function=f"session:{session_id}",
            event_type="mutation",
            target=target,
            metadata={"tool_name": tool_name, "source": "generic_webhook"},
        )
