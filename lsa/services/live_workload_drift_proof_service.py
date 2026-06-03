from __future__ import annotations

import contextlib
import contextvars
import importlib.util
import inspect
import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any
import types
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from lsa.drift.trace_parser import load_trace_events
from lsa.services.live_workload_target_profile_service import LiveWorkloadTargetProfileService, resolve_target_headers
from lsa.services.secret_reference_service import SecretReferenceService


_request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("lsa_request_id", default=None)
_trace_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("lsa_trace_id", default=None)
_drift_ctx: contextvars.ContextVar[bool] = contextvars.ContextVar("lsa_drift_mode", default=False)
_trace_lock = threading.Lock()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class _MockHandler(BaseHTTPRequestHandler):
    server_version = "LSAWorkloadProof/1.0"

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            self.rfile.read(length)
        payload = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


@dataclass(slots=True)
class _MockServer:
    name: str
    server: ThreadingHTTPServer
    thread: threading.Thread

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def url(self, path: str) -> str:
        if path.startswith("/"):
            return f"{self.base_url}{path}"
        return f"{self.base_url}/{path}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@dataclass(slots=True)
class _SimpleResponse:
    status_code: int


@dataclass(slots=True)
class _ExternalServer:
    name: str
    base_url: str

    def url(self, path: str) -> str:
        if path.startswith("/"):
            return f"{self.base_url}{path}"
        return f"{self.base_url}/{path}"


@dataclass(slots=True)
class _ResolvedTargetPair:
    target_mode: str
    target_profile: str
    approved_base_url: str | None
    drift_base_url: str | None
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_mode": self.target_mode,
            "target_profile": self.target_profile,
            "approved_target_base_url": self.approved_base_url,
            "drift_target_base_url": self.drift_base_url,
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
        }


@contextlib.contextmanager
def _mock_server(name: str) -> Any:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockHandler)
    thread = threading.Thread(target=server.serve_forever, name=f"lsa-{name}-mock", daemon=True)
    thread.start()
    wrapped = _MockServer(name=name, server=server, thread=thread)
    try:
        yield wrapped
    finally:
        wrapped.close()


def _load_sample_service_module(sample_root: Path) -> Any:
    module_path = sample_root / "app.py"
    spec = importlib.util.spec_from_file_location(f"lsa_sample_service_{uuid4().hex}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load sample service module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass(slots=True)
class LiveWorkloadDriftProofSummary:
    proof_id: str
    executed_at: str
    changed_by: str
    reason: str | None
    environment_name: str
    sample_service_path: str
    snapshot_id: str | None
    snapshot_path: str
    audit_id: str | None
    trace_path: str
    target_mode: str
    target_profile: str
    approved_target_base_url: str | None
    drift_target_base_url: str | None
    event_count: int
    alert_count: int
    passed: bool
    unexpected_targets: list[str]
    impacted_functions: list[str]
    report_paths: list[str]
    explanation: dict[str, Any]
    maintenance_event_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "executed_at": self.executed_at,
            "changed_by": self.changed_by,
            "reason": self.reason,
            "environment_name": self.environment_name,
            "sample_service_path": self.sample_service_path,
            "snapshot_id": self.snapshot_id,
            "snapshot_path": self.snapshot_path,
            "audit_id": self.audit_id,
            "trace_path": self.trace_path,
            "target_mode": self.target_mode,
            "target_profile": self.target_profile,
            "approved_target_base_url": self.approved_target_base_url,
            "drift_target_base_url": self.drift_target_base_url,
            "event_count": self.event_count,
            "alert_count": self.alert_count,
            "passed": self.passed,
            "unexpected_targets": list(self.unexpected_targets),
            "impacted_functions": list(self.impacted_functions),
            "report_paths": list(self.report_paths),
            "explanation": dict(self.explanation),
            "maintenance_event_id": self.maintenance_event_id,
        }


@dataclass(slots=True)
class LiveWorkloadDriftProofService:
    settings: Any
    ingest_service: Any
    audit_service: Any
    job_service: Any

    def _secret_lookup(self, alias: str) -> str | None:
        return SecretReferenceService(self.settings.secret_aliases_path).resolve_secret_alias(alias)

    def describe_target_pair(
        self,
        *,
        target_profile_name: str | None = None,
        approved_base_url: str | None = None,
        drift_base_url: str | None = None,
    ) -> dict[str, Any]:
        return self._resolve_target_pair(
            target_profile_name=target_profile_name,
            approved_base_url=approved_base_url,
            drift_base_url=drift_base_url,
        ).to_dict()

    def probe_target_pair(
        self,
        *,
        timeout_seconds: float = 10.0,
        target_profile_name: str | None = None,
        approved_base_url: str | None = None,
        drift_base_url: str | None = None,
    ) -> dict[str, Any]:
        target_pair = self._resolve_target_pair(
            target_profile_name=target_profile_name,
            approved_base_url=approved_base_url,
            drift_base_url=drift_base_url,
        )
        results: dict[str, Any] = {}
        blockers: list[str] = []
        passed = True
        effective_timeout = target_pair.request_timeout_seconds or timeout_seconds
        with self._target_server("approved", target_pair.approved_base_url) as approved_server, self._target_server(
            "drift",
            target_pair.drift_base_url,
        ) as drift_server:
            for name, server in (("approved", approved_server), ("drift", drift_server)):
                url = (
                    target_pair.approved_probe_url
                    if name == "approved"
                    else target_pair.drift_probe_url
                ) or server.url(f"/probe/{name}")
                method = (
                    target_pair.approved_probe_method
                    if name == "approved"
                    else target_pair.drift_probe_method
                ) or ("GET" if target_pair.target_mode == "external" else "POST")
                expected_statuses = (
                    target_pair.approved_expected_statuses
                    if name == "approved"
                    else target_pair.drift_expected_statuses
                ) or [200]
                raw_headers = target_pair.approved_headers if name == "approved" else target_pair.drift_headers
                headers, missing_env = resolve_target_headers(raw_headers, secret_lookup=self._secret_lookup)
                started_at = datetime.now(UTC)
                status_code: int | None = None
                error: str | None = None
                try:
                    if missing_env:
                        raise RuntimeError(f"Missing environment variables: {', '.join(sorted(missing_env))}")
                    body = b"{}" if method in {"POST", "PUT", "PATCH", "DELETE"} else None
                    request = Request(url, data=body, method=method)
                    if body is not None:
                        request.add_header("Content-Type", "application/json")
                    for header_name, header_value in headers.items():
                        request.add_header(header_name, header_value)
                    with urlopen(request, timeout=effective_timeout) as response:
                        status_code = int(response.status)
                except Exception as exc:  # noqa: BLE001
                    error = str(exc)
                    passed = False
                    blockers.append(f"{name}_target_unreachable")
                completed_at = datetime.now(UTC)
                latency_ms = max((completed_at - started_at).total_seconds() * 1000.0, 0.0)
                status_ok = status_code in expected_statuses if status_code is not None else False
                results[name] = {
                    "url": url,
                    "method": method,
                    "expected_statuses": list(expected_statuses),
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                    "status": "passed" if status_ok and error is None else "failed",
                    "error": error,
                }
                if not status_ok and error is None:
                    passed = False
                    blockers.append(f"{name}_target_status")
        return {
            **target_pair.to_dict(),
            "status": "passed" if passed else "failed",
            "timeout_seconds": effective_timeout,
            "results": results,
            "blockers": blockers,
        }

    def run(
        self,
        *,
        changed_by: str,
        reason: str | None = None,
        persist: bool = True,
        snapshot_id: str | None = None,
        audit_id: str | None = None,
        actor_details: dict | None = None,
        target_profile_name: str | None = None,
        approved_base_url: str | None = None,
        drift_base_url: str | None = None,
    ) -> LiveWorkloadDriftProofSummary:
        proof_id = uuid4().hex[:12]
        executed_at = _utc_now()
        sample_root = (Path(self.settings.root_dir) / "lsa" / "examples" / "noisy_service").resolve()
        resolved_snapshot_id = snapshot_id or f"live-workload-proof-{proof_id}"
        resolved_audit_id = audit_id or f"live-workload-proof-audit-{proof_id}"
        self.settings.traces_dir.mkdir(parents=True, exist_ok=True)
        trace_path = self.settings.traces_dir / f"live-workload-proof-{proof_id}.log"
        if trace_path.exists():
            trace_path.unlink()
        snapshot_output_path = self.settings.traces_dir / f"live-workload-proof-{proof_id}-snapshot.json"

        ingest_result = self.ingest_service.ingest(
            str(sample_root),
            persist=persist,
            output_path=str(snapshot_output_path) if not persist else None,
            snapshot_id=resolved_snapshot_id if persist else None,
        )
        resolved_snapshot_path = ingest_result.snapshot_path or ""

        target_pair = self._resolve_target_pair(
            target_profile_name=target_profile_name,
            approved_base_url=approved_base_url,
            drift_base_url=drift_base_url,
        )
        with TemporaryDirectory(prefix="lsa-live-workload-proof-") as temp_dir:
            with self._target_server("approved", target_pair.approved_base_url) as approved_server, self._target_server(
                "drift",
                target_pair.drift_base_url,
            ) as drift_server:
                default_timeout = 20.0 if target_pair.target_profile == "public-echo-pair" else 5.0
                requests_stub = types.ModuleType("requests")

                def traced_post(url: str, *args: Any, **kwargs: Any) -> _SimpleResponse:
                    function_name = self._resolve_calling_function()
                    trace_id = _trace_id_ctx.get() or uuid4().hex[:32]
                    request_id = _request_id_ctx.get() or f"req-{uuid4().hex[:8]}"
                    drift_mode = _drift_ctx.get()
                    reported_url = url
                    actual_url = self._map_actual_url(
                        url=url,
                        function_name=function_name,
                        drift_mode=drift_mode,
                        approved_action_url=target_pair.approved_action_url,
                        drift_action_url=target_pair.drift_action_url,
                        approved_server=approved_server,
                        drift_server=drift_server,
                    )
                    if drift_mode and function_name == "charge_customer":
                        reported_url = "https://malicious.example.com/exfil"
                    span_id = uuid4().hex[:16]
                    trace_line = (
                        f"event=network process=python comm=python module=app function_name={function_name} "
                        f"request_id={request_id} traceparent=00-{trace_id}-{span_id}-01 target={reported_url}"
                    )
                    with _trace_lock:
                        with trace_path.open("a", encoding="utf-8") as handle:
                            handle.write(trace_line)
                            handle.write("\n")
                    timeout = float(kwargs.pop("timeout", default_timeout))
                    timeout = float(target_pair.request_timeout_seconds or timeout)
                    kwargs.pop("verify", None)
                    body = None
                    if "json" in kwargs:
                        body = json.dumps(kwargs["json"]).encode("utf-8")
                    elif "data" in kwargs:
                        body = str(kwargs["data"]).encode("utf-8")
                    method = (
                        target_pair.drift_action_method
                        if drift_mode and function_name == "charge_customer"
                        else target_pair.approved_action_method
                    ) or ("GET" if target_pair.target_mode == "external" else "POST")
                    header_source = (
                        target_pair.drift_headers
                        if drift_mode and function_name == "charge_customer"
                        else target_pair.approved_headers
                    )
                    headers, missing_env = resolve_target_headers(header_source, secret_lookup=self._secret_lookup)
                    if missing_env:
                        raise RuntimeError(f"Missing environment variables: {', '.join(sorted(missing_env))}")
                    request = Request(
                        actual_url,
                        data=body if method in {"POST", "PUT", "PATCH", "DELETE"} else None,
                        method=method,
                    )
                    if method in {"POST", "PUT", "PATCH", "DELETE"}:
                        request.add_header("Content-Type", "application/json")
                    for header_name, header_value in headers.items():
                        request.add_header(header_name, header_value)
                    with urlopen(request, timeout=timeout) as response:
                        return _SimpleResponse(status_code=int(response.status))

                requests_stub.post = traced_post
                original_requests_module = sys.modules.get("requests")
                sys.modules["requests"] = requests_stub
                try:
                    sample_app = _load_sample_service_module(sample_root)
                    self._run_noisy_workload(sample_app=sample_app, proof_id=proof_id)
                finally:
                    if original_requests_module is None:
                        sys.modules.pop("requests", None)
                    else:
                        sys.modules["requests"] = original_requests_module

            events = load_trace_events(trace_path, trace_format="auto")
            audit_result = self.audit_service.audit(
                events=events,
                snapshot_id=resolved_snapshot_id if persist else None,
                snapshot_path=None if persist else resolved_snapshot_path,
                persist=persist,
                audit_id=resolved_audit_id if persist else None,
            )

            explanation = audit_result.explanation.to_dict()
            passed = (
                audit_result.explanation.alert_count >= 1
                and "malicious.example.com" in audit_result.explanation.unexpected_targets
                and "charge_customer" in audit_result.explanation.impacted_functions
            )
            summary = LiveWorkloadDriftProofSummary(
                proof_id=proof_id,
                executed_at=executed_at,
                changed_by=changed_by,
                reason=reason,
                environment_name=self.settings.environment_name,
                sample_service_path=str(sample_root),
                snapshot_id=audit_result.snapshot_record.snapshot_id if audit_result.snapshot_record else resolved_snapshot_id,
                snapshot_path=audit_result.snapshot_path or resolved_snapshot_path,
                audit_id=audit_result.record.audit_id if audit_result.record else resolved_audit_id,
                trace_path=str(trace_path),
                target_mode=target_pair.target_mode,
                target_profile=target_pair.target_profile,
                approved_target_base_url=target_pair.approved_base_url,
                drift_target_base_url=target_pair.drift_base_url,
                event_count=len(events),
                alert_count=len(audit_result.alerts),
                passed=passed,
                unexpected_targets=list(explanation.get("unexpected_targets", [])),
                impacted_functions=list(explanation.get("impacted_functions", [])),
                report_paths=list(audit_result.report_paths),
                explanation=explanation,
            )

        event = self.job_service.record_maintenance_event(
            event_type="live_workload_drift_proof_executed",
            changed_by=changed_by,
            reason=reason,
            details=summary.to_dict(),
            actor_details=actor_details,
        )
        summary.maintenance_event_id = event.event_id
        return summary

    def _resolve_target_pair(
        self,
        *,
        target_profile_name: str | None = None,
        approved_base_url: str | None = None,
        drift_base_url: str | None = None,
    ) -> _ResolvedTargetPair:
        approved = (approved_base_url or self.settings.workload_proof_approved_base_url or "").strip().rstrip("/")
        drift = (drift_base_url or self.settings.workload_proof_drift_base_url or "").strip().rstrip("/")
        if approved and drift:
            profile = target_profile_name or self.settings.workload_proof_target_profile
            if profile in {"", "embedded"}:
                profile = "custom-external-pair"
            return _ResolvedTargetPair(
                target_mode="external",
                target_profile=profile,
                approved_base_url=approved,
                drift_base_url=drift,
                approved_probe_url=None,
                drift_probe_url=None,
                approved_action_url=approved,
                drift_action_url=drift,
                approved_probe_method="GET",
                drift_probe_method="GET",
                approved_action_method="GET",
                drift_action_method="GET",
                approved_expected_statuses=[200],
                drift_expected_statuses=[200],
            )
        profile = LiveWorkloadTargetProfileService(self.settings).resolve(
            target_profile_name or self.settings.workload_proof_target_profile
        )
        if profile is not None:
            return _ResolvedTargetPair(
                target_mode="external",
                target_profile=profile.name,
                approved_base_url=profile.approved_base_url,
                drift_base_url=profile.drift_base_url,
                approved_probe_url=profile.approved_probe_url,
                drift_probe_url=profile.drift_probe_url,
                approved_action_url=profile.approved_action_url,
                drift_action_url=profile.drift_action_url,
                approved_probe_method=profile.approved_probe_method,
                drift_probe_method=profile.drift_probe_method,
                approved_action_method=profile.approved_action_method,
                drift_action_method=profile.drift_action_method,
                approved_headers=profile.approved_headers,
                drift_headers=profile.drift_headers,
                approved_expected_statuses=profile.approved_expected_statuses,
                drift_expected_statuses=profile.drift_expected_statuses,
                request_timeout_seconds=profile.request_timeout_seconds,
            )
        return _ResolvedTargetPair(
            target_mode="embedded",
            target_profile="embedded",
            approved_base_url=None,
            drift_base_url=None,
        )

    @contextlib.contextmanager
    def _target_server(self, name: str, base_url: str | None) -> Any:
        if base_url:
            yield _ExternalServer(name=name, base_url=base_url.rstrip("/"))
            return
        with _mock_server(name) as server:
            yield server

    def _run_charge(self, sample_app: Any, *, amount: int, request_id: str, trace_id: str, drift_mode: bool) -> None:
        request_token = _request_id_ctx.set(request_id)
        trace_token = _trace_id_ctx.set(trace_id)
        drift_token = _drift_ctx.set(drift_mode)
        try:
            sample_app.charge_customer(amount)
        finally:
            _drift_ctx.reset(drift_token)
            _trace_id_ctx.reset(trace_token)
            _request_id_ctx.reset(request_token)

    def _run_refund(self, sample_app: Any, *, amount: int, request_id: str, trace_id: str) -> None:
        request_token = _request_id_ctx.set(request_id)
        trace_token = _trace_id_ctx.set(trace_id)
        drift_token = _drift_ctx.set(False)
        try:
            sample_app.refund_customer(amount)
        finally:
            _drift_ctx.reset(drift_token)
            _trace_id_ctx.reset(trace_token)
            _request_id_ctx.reset(request_token)

    def _run_notify(self, sample_app: Any, *, email: str, request_id: str, trace_id: str) -> None:
        request_token = _request_id_ctx.set(request_id)
        trace_token = _trace_id_ctx.set(trace_id)
        drift_token = _drift_ctx.set(False)
        try:
            sample_app.notify_customer(email)
        finally:
            _drift_ctx.reset(drift_token)
            _trace_id_ctx.reset(trace_token)
            _request_id_ctx.reset(request_token)

    def _run_sync_ledger(
        self,
        sample_app: Any,
        *,
        entry_id: str,
        amount: int,
        request_id: str,
        trace_id: str,
    ) -> None:
        request_token = _request_id_ctx.set(request_id)
        trace_token = _trace_id_ctx.set(trace_id)
        drift_token = _drift_ctx.set(False)
        try:
            sample_app.sync_ledger(entry_id, amount)
        finally:
            _drift_ctx.reset(drift_token)
            _trace_id_ctx.reset(trace_token)
            _request_id_ctx.reset(request_token)

    def _run_emit_analytics(
        self,
        sample_app: Any,
        *,
        event_name: str,
        customer_id: str,
        request_id: str,
        trace_id: str,
    ) -> None:
        request_token = _request_id_ctx.set(request_id)
        trace_token = _trace_id_ctx.set(trace_id)
        drift_token = _drift_ctx.set(False)
        try:
            sample_app.emit_analytics(event_name, customer_id)
        finally:
            _drift_ctx.reset(drift_token)
            _trace_id_ctx.reset(trace_token)
            _request_id_ctx.reset(request_token)

    def _run_noisy_workload(self, *, sample_app: Any, proof_id: str) -> None:
        safe_payment_trace = uuid4().hex[:32]
        safe_payment_request = f"req-{proof_id}-safe-payment"
        self._run_charge(sample_app, amount=100, request_id=safe_payment_request, trace_id=safe_payment_trace, drift_mode=False)
        self._run_sync_ledger(
            sample_app,
            entry_id=f"ledger-{proof_id}-safe",
            amount=100,
            request_id=safe_payment_request,
            trace_id=safe_payment_trace,
        )
        self._run_notify(
            sample_app,
            email="safe@example.com",
            request_id=safe_payment_request,
            trace_id=safe_payment_trace,
        )

        refund_trace = uuid4().hex[:32]
        refund_request = f"req-{proof_id}-refund"
        self._run_refund(sample_app, amount=25, request_id=refund_request, trace_id=refund_trace)
        self._run_notify(
            sample_app,
            email="refund@example.com",
            request_id=refund_request,
            trace_id=refund_trace,
        )

        for index in range(3):
            analytics_trace = uuid4().hex[:32]
            analytics_request = f"req-{proof_id}-analytics-{index}"
            self._run_emit_analytics(
                sample_app,
                event_name=f"checkout_step_{index}",
                customer_id=f"cust-{index}",
                request_id=analytics_request,
                trace_id=analytics_trace,
            )

        drift_trace = uuid4().hex[:32]
        drift_request = f"req-{proof_id}-drift"
        self._run_charge(sample_app, amount=101, request_id=drift_request, trace_id=drift_trace, drift_mode=True)
        self._run_sync_ledger(
            sample_app,
            entry_id=f"ledger-{proof_id}-drift",
            amount=101,
            request_id=drift_request,
            trace_id=drift_trace,
        )
        self._run_notify(
            sample_app,
            email="drift@example.com",
            request_id=drift_request,
            trace_id=drift_trace,
        )
        self._run_emit_analytics(
            sample_app,
            event_name="checkout_complete",
            customer_id="cust-drift",
            request_id=drift_request,
            trace_id=drift_trace,
        )

    def _resolve_calling_function(self) -> str:
        for frame_info in inspect.stack()[1:]:
            function_name = frame_info.function
            if function_name in {
                "charge_customer",
                "refund_customer",
                "notify_customer",
                "sync_ledger",
                "emit_analytics",
            }:
                return function_name
        return "unknown"

    def _map_actual_url(
        self,
        *,
        url: str,
        function_name: str,
        drift_mode: bool,
        approved_action_url: str | None,
        drift_action_url: str | None,
        approved_server: _MockServer | _ExternalServer,
        drift_server: _MockServer | _ExternalServer,
    ) -> str:
        if drift_mode and function_name == "charge_customer":
            return drift_action_url or drift_server.url("/exfil")
        if approved_action_url:
            return approved_action_url
        host = urlparse(url).netloc
        if host == "api.stripe.com":
            if function_name == "refund_customer":
                return approved_server.url("/v1/refunds")
            return approved_server.url("/v1/charges")
        if host == "api.mailgun.net":
            return approved_server.url("/v3/messages")
        if host == "ledger.internal":
            return approved_server.url("/v1/entries")
        if host == "api.segment.io":
            return approved_server.url("/v1/track")
        if host == "malicious.example.com":
            return drift_server.url("/exfil")
        return url
