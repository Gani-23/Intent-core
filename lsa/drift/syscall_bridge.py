#!/usr/bin/env python3
"""Kernel-level process observation bridge.

Provides a second, unfakeable observation channel that operates independently
of what the agent reports through the hook interface. An agent that bypasses
hooks still shows up in the syscall/filesystem event stream.

Platform support:
- macOS: fs_usage -w -f filesys -p <pid> (no SIP bypass needed)
- Linux: bpftrace if available, else /proc/<pid>/fd polling
- Fallback: ObservationMode.UNAVAILABLE — clean degradation, never crashes.

This module does NOT block tool calls and does NOT log file contents —
it only records metadata: path, op, pid, timestamp.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from lsa.drift.models import ObservationMode, ObservedEvent

# ── platform detection ────────────────────────────────────────────────────────
_IS_MACOS = sys.platform == "darwin"
_IS_LINUX = sys.platform.startswith("linux")
_HAS_BPFTRACE = bool(shutil.which("bpftrace"))
_HAS_FS_USAGE = bool(shutil.which("fs_usage"))


@dataclass
class BridgeCapability:
    mode: str
    available: bool
    reason: str


def detect_capability() -> BridgeCapability:
    """Probe what level of kernel observation is available."""
    if _IS_LINUX and _HAS_BPFTRACE:
        return BridgeCapability(ObservationMode.FULL, True, "bpftrace available on Linux")
    if _IS_MACOS and _HAS_FS_USAGE:
        return BridgeCapability(ObservationMode.FILESYSTEM, True, "fs_usage available on macOS")
    if _IS_LINUX:
        return BridgeCapability(ObservationMode.FILESYSTEM, True, "proc/fd polling on Linux")
    return BridgeCapability(ObservationMode.UNAVAILABLE, False,
                            "No kernel tracing available (SIP on, no bpftrace, no fs_usage)")


# ── macOS fs_usage parser ─────────────────────────────────────────────────────
_FS_USAGE_LINE = re.compile(
    r"(?P<op>open|write|create|rename|unlink|read)\s+.*?(?P<path>/[\S]+)", re.I
)

_OP_NORM = {
    "open": "READ", "read": "READ",
    "write": "WRITE", "create": "WRITE",
    "rename": "WRITE", "unlink": "DELETE",
}


def _parse_fs_usage_line(line: str) -> ObservedEvent | None:
    m = _FS_USAGE_LINE.search(line)
    if not m:
        return None
    op_raw = m.group("op").lower()
    path = m.group("path")
    op = _OP_NORM.get(op_raw, "OTHER")
    return ObservedEvent(
        function="syscall:fs_usage",
        event_type="syscall",
        target=path,
        metadata={"op": op, "raw_op": op_raw, "source": "fs_usage"},
    )


def observe_pid_macos(pid: int, duration_seconds: float = 5.0) -> list[ObservedEvent]:
    """Run fs_usage against a PID for a fixed duration. Returns captured events."""
    if not _HAS_FS_USAGE:
        return []
    events: list[ObservedEvent] = []
    try:
        proc = subprocess.Popen(
            ["fs_usage", "-w", "-f", "filesys", "-p", str(pid)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        deadline = time.monotonic() + duration_seconds
        assert proc.stdout is not None
        for line in proc.stdout:
            if time.monotonic() > deadline:
                break
            ev = _parse_fs_usage_line(line)
            if ev:
                events.append(ev)
        proc.terminate()
    except (PermissionError, FileNotFoundError, subprocess.SubprocessError):
        pass
    return events


# ── Linux /proc polling ───────────────────────────────────────────────────────
def _poll_proc_fd(pid: int) -> list[ObservedEvent]:
    """Snapshot /proc/<pid>/fd symlinks to detect open file handles."""
    events: list[ObservedEvent] = []
    fd_dir = Path(f"/proc/{pid}/fd")
    if not fd_dir.exists():
        return events
    for fd in fd_dir.iterdir():
        try:
            target = str(fd.resolve())
            if target.startswith("/"):
                events.append(ObservedEvent(
                    function="syscall:proc_fd",
                    event_type="syscall",
                    target=target,
                    metadata={"op": "OPEN", "source": "proc_fd"},
                ))
        except (PermissionError, OSError):
            continue
    return events


# ── bpftrace (Linux full) ─────────────────────────────────────────────────────
_BPFT_SCRIPT = """
tracepoint:syscalls:sys_enter_openat,
tracepoint:syscalls:sys_enter_write,
tracepoint:syscalls:sys_enter_unlinkat
/pid == TARGET_PID/
{
    printf("%s %s\\n", probe, str(args->filename));
}
"""

def observe_pid_linux_bpftrace(pid: int, duration_seconds: float = 5.0) -> list[ObservedEvent]:
    if not _HAS_BPFTRACE:
        return []
    script = _BPFT_SCRIPT.replace("TARGET_PID", str(pid))
    events: list[ObservedEvent] = []
    try:
        result = subprocess.run(
            ["bpftrace", "-e", script, "--timeout", str(int(duration_seconds))],
            capture_output=True, text=True, timeout=duration_seconds + 2,
        )
        for line in result.stdout.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                raw_probe, path = parts
                op = "READ" if "openat" in raw_probe else ("WRITE" if "write" in raw_probe else "DELETE")
                events.append(ObservedEvent(
                    function="syscall:bpftrace",
                    event_type="syscall",
                    target=path,
                    metadata={"op": op, "probe": raw_probe, "source": "bpftrace"},
                ))
    except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return events


# ── public API ────────────────────────────────────────────────────────────────
def observe_process(pid: int, duration_seconds: float = 5.0) -> tuple[list[ObservedEvent], str]:
    """Observe a process using the best available mechanism.

    Returns (events, observation_mode).
    Never raises — always returns a valid list (possibly empty).
    """
    cap = detect_capability()
    if not cap.available:
        return [], ObservationMode.UNAVAILABLE

    if _IS_LINUX and _HAS_BPFTRACE:
        return observe_pid_linux_bpftrace(pid, duration_seconds), ObservationMode.FULL
    if _IS_MACOS and _HAS_FS_USAGE:
        return observe_pid_macos(pid, duration_seconds), ObservationMode.FILESYSTEM
    if _IS_LINUX:
        return _poll_proc_fd(pid), ObservationMode.FILESYSTEM
    return [], ObservationMode.UNAVAILABLE
