from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib import error, request

from lsa.core.models import FunctionIntent
from lsa.drift.models import DriftAlert, RemediationReport, TraceSessionSummary


class RemediationClient(Protocol):
    def analyze(
        self,
        function: FunctionIntent,
        alert: DriftAlert,
        prompt: str,
        session: TraceSessionSummary | None = None,
    ) -> RemediationReport: ...


@dataclass(slots=True)
class RemediationRuntimeStatus:
    provider: str
    model: str | None
    base_url: str | None
    enabled: bool
    available: bool
    fallback_active: bool
    configured: bool
    blockers: list[str]


class RuleBasedLLMClient:
    """Small deterministic stand-in until a real remediation model is configured."""

    def analyze(
        self,
        function: FunctionIntent,
        alert: DriftAlert,
        prompt: str,
        session: TraceSessionSummary | None = None,
    ) -> RemediationReport:
        expected = ", ".join(alert.expected_targets) or "no recorded targets"
        summary = (
            f"{function.qualname} reached {alert.observed_target}, which does not match "
            f"the current intent graph. The closest known outbound set is {expected}."
        )
        immediate_action = (
            "Verify whether the new outbound call was intentionally introduced. "
            "If not, disable or roll back the change and inspect recent deploys."
        )
        long_term_fix = (
            "Either update the code to remove the unintended dependency or update the "
            "intent graph generation path so the change is reviewed and recorded explicitly."
        )
        supporting_facts = [
            f"Prompt used for remediation: {prompt}",
            f"Known external hosts: {expected}",
            f"Observed target: {alert.observed_target}",
        ]
        if session is not None:
            supporting_facts.append(
                f"Session {session.session_key} observed {session.event_count} events across targets: "
                f"{', '.join(session.targets)}"
            )
        return RemediationReport(
            function=function.qualname,
            title=f"Drift report for {function.qualname}",
            summary=summary,
            risk=alert.severity.upper(),
            immediate_action=immediate_action,
            long_term_fix=long_term_fix,
            supporting_facts=supporting_facts,
        )


class OpenAICompatibleRemediationClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None,
        timeout_seconds: float = 30.0,
        fallback_client: RemediationClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.fallback_client = fallback_client or RuleBasedLLMClient()

    def analyze(
        self,
        function: FunctionIntent,
        alert: DriftAlert,
        prompt: str,
        session: TraceSessionSummary | None = None,
    ) -> RemediationReport:
        try:
            payload = self._invoke(prompt)
            return self._build_report(function=function, alert=alert, session=session, prompt=prompt, payload=payload)
        except Exception as exc:
            report = self.fallback_client.analyze(function, alert, prompt, session=session)
            report.supporting_facts.append(f"Model fallback activated: {type(exc).__name__}: {exc}")
            return report

    def _invoke(self, prompt: str) -> dict:
        body = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a production incident remediation assistant. "
                        "Return strict JSON with keys: summary, risk, immediate_action, long_term_fix, supporting_facts."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        }
        encoded = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=encoded,
            headers=headers,
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
        response_payload = json.loads(raw)
        choices = response_payload.get("choices") or []
        if not choices:
            raise ValueError("Model returned no choices.")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Model returned empty content.")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("Model did not return valid JSON content.") from exc

    def _build_report(
        self,
        *,
        function: FunctionIntent,
        alert: DriftAlert,
        session: TraceSessionSummary | None,
        prompt: str,
        payload: dict,
    ) -> RemediationReport:
        supporting_facts = payload.get("supporting_facts")
        if not isinstance(supporting_facts, list):
            supporting_facts = []
        normalized_facts = [str(item) for item in supporting_facts if str(item).strip()]
        normalized_facts.append(f"Model provider: openai-compatible")
        normalized_facts.append(f"Model name: {self.model}")
        normalized_facts.append(f"Prompt used for remediation: {prompt}")
        if session is not None:
            normalized_facts.append(
                f"Session {session.session_key} observed {session.event_count} events across targets: "
                f"{', '.join(session.targets)}"
            )
        return RemediationReport(
            function=function.qualname,
            title=f"Drift report for {function.qualname}",
            summary=str(payload.get("summary") or ""),
            risk=str(payload.get("risk") or alert.severity.upper()),
            immediate_action=str(payload.get("immediate_action") or ""),
            long_term_fix=str(payload.get("long_term_fix") or ""),
            supporting_facts=normalized_facts,
        )


def inspect_remediation_runtime(settings: object) -> RemediationRuntimeStatus:
    provider = str(getattr(settings, "remediation_provider", "rule-based") or "rule-based").strip().lower()
    model = getattr(settings, "remediation_model", None)
    base_url = getattr(settings, "remediation_base_url", None)
    enable = bool(getattr(settings, "enable_remediation_model", False))
    fallback_enabled = bool(getattr(settings, "remediation_fallback_enabled", True))
    blockers: list[str] = []
    configured = False
    available = False
    if provider == "rule-based" or not enable:
        configured = provider == "rule-based" or not enable
        available = True
        return RemediationRuntimeStatus(
            provider="rule-based",
            model=None,
            base_url=None,
            enabled=enable,
            available=available,
            fallback_active=False,
            configured=configured,
            blockers=blockers,
        )
    if provider != "openai-compatible":
        blockers.append("Unsupported remediation provider configured.")
    if not base_url:
        blockers.append("Remediation base URL is not configured.")
    if not model:
        blockers.append("Remediation model name is not configured.")
    configured = not blockers
    available = configured
    return RemediationRuntimeStatus(
        provider=provider,
        model=model,
        base_url=base_url,
        enabled=enable,
        available=available,
        fallback_active=fallback_enabled,
        configured=configured,
        blockers=blockers,
    )


def build_remediation_client(settings: object) -> RemediationClient:
    status = inspect_remediation_runtime(settings)
    fallback_client = RuleBasedLLMClient()
    if status.provider == "rule-based" or not status.available:
        return fallback_client
    if status.provider == "openai-compatible":
        return OpenAICompatibleRemediationClient(
            base_url=str(status.base_url),
            model=str(status.model),
            api_key=getattr(settings, "remediation_api_key", None),
            timeout_seconds=float(getattr(settings, "remediation_timeout_seconds", 30.0)),
            fallback_client=fallback_client,
        )
    return fallback_client
