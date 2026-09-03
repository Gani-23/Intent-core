from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from lsa.core.models import FunctionIntent
from lsa.drift.models import DriftAlert, RemediationReport, TraceSessionSummary
from lsa.remediation.failsafe import (
    call_ai_json_with_failsafe,
    call_anthropic_json,
    call_gemini_json,
    call_openai_json,
    get_available_ai_providers,
)


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


def _build_report_common(
    *,
    provider: str,
    model_name: str | None,
    function: FunctionIntent,
    alert: DriftAlert,
    session: TraceSessionSummary | None,
    prompt: str,
    payload: dict,
) -> RemediationReport:
    facts = [str(x) for x in payload.get("supporting_facts", []) if str(x).strip()] if isinstance(payload.get("supporting_facts"), list) else []
    facts.extend([f"Model provider: {provider}", f"Prompt used for remediation: {prompt}"])
    if model_name:
        facts.append(f"Model name: {model_name}")
    if session is not None:
        facts.append(
            f"Session {session.session_key} observed {session.event_count} events across targets: {', '.join(session.targets)}"
        )
    raw_risk = str(payload.get("risk") or alert.severity.upper()).upper()
    risk = "CRITICAL" if "CRIT" in raw_risk else "HIGH" if "HIGH" in raw_risk else "MEDIUM" if "MED" in raw_risk else "LOW"
    return RemediationReport(
        function=function.qualname,
        title=f"Drift report for {function.qualname}",
        summary=str(payload.get("summary") or ""),
        risk=risk,
        immediate_action=str(payload.get("immediate_action") or ""),
        long_term_fix=str(payload.get("long_term_fix") or ""),
        supporting_facts=facts,
    )


class RuleBasedLLMClient:
    """Deterministic stand-in used when offline, uncredentialed, or as final fallback."""

    def analyze(
        self,
        function: FunctionIntent,
        alert: DriftAlert,
        prompt: str,
        session: TraceSessionSummary | None = None,
    ) -> RemediationReport:
        expected = ", ".join(alert.expected_targets) or "no recorded in-scope targets"
        summary = f"{function.qualname} triggered an alert on {alert.observed_target}. {alert.reason}"
        immediate_action = (
            "Critical/high severity: pause and confirm with the human before this goes further "
            "-- verify whether this was actually intended. Medium severity: note it and continue, "
            "but flag it in the session summary for review."
        )
        long_term_fix = (
            "If this was a false positive, add the target to the session's known scope. If it "
            "was real drift, tighten the task description or the tool's permission scope so this "
            "class of action can't happen silently again."
        )
        supporting_facts = [
            f"Prompt used for remediation: {prompt}",
            f"In-scope targets at time of alert: {expected}",
            f"Observed target: {alert.observed_target}",
        ]
        if session is not None:
            supporting_facts.append(
                f"Session {session.session_key} observed {session.event_count} events across targets: {', '.join(session.targets)}"
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


def call_claude_json(
    *,
    model: str,
    api_key: str | None,
    base_url: str,
    system: str,
    user_prompt: str,
    timeout_seconds: float = 30.0,
    max_tokens: int = 1024,
) -> dict:
    """Shared entrypoint for Claude Messages API parsing, backed by failsafe."""
    return call_anthropic_json(
        model=model,
        api_key=api_key,
        base_url=base_url,
        system=system,
        user_prompt=user_prompt,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
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
            payload = call_openai_json(
                system=(
                    "You are a production incident remediation assistant. "
                    "Return strict JSON with keys: summary, risk, immediate_action, long_term_fix, supporting_facts."
                ),
                user_prompt=prompt,
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url,
                timeout_seconds=self.timeout_seconds,
            )
            return _build_report_common(
                provider="openai-compatible",
                model_name=self.model,
                function=function,
                alert=alert,
                session=session,
                prompt=prompt,
                payload=payload,
            )
        except Exception as exc:
            report = self.fallback_client.analyze(function, alert, prompt, session=session)
            report.supporting_facts.append(f"Model fallback activated: {type(exc).__name__}: {exc}")
            return report


class AnthropicRemediationClient:
    def __init__(
        self,
        *,
        model: str,
        api_key: str | None,
        base_url: str = "https://api.anthropic.com",
        timeout_seconds: float = 30.0,
        fallback_client: RemediationClient | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
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
            payload = call_claude_json(
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url,
                system=(
                    "You are a production incident remediation assistant. Return strict JSON "
                    "with keys: summary, risk, immediate_action, long_term_fix, supporting_facts."
                ),
                user_prompt=prompt,
                timeout_seconds=self.timeout_seconds,
            )
            return _build_report_common(
                provider="anthropic",
                model_name=self.model,
                function=function,
                alert=alert,
                session=session,
                prompt=prompt,
                payload=payload,
            )
        except Exception as exc:
            report = self.fallback_client.analyze(function, alert, prompt, session=session)
            report.supporting_facts.append(f"Model fallback activated: {type(exc).__name__}: {exc}")
            return report


class FailsafeRemediationClient:
    """Cascading multi-provider client: Anthropic -> OpenAI -> Gemini -> Antigravity -> RuleBased."""

    def __init__(
        self,
        *,
        preferred_provider: str | None = None,
        timeout_seconds: float = 20.0,
        fallback_client: RemediationClient | None = None,
    ) -> None:
        self.preferred_provider = preferred_provider
        self.timeout_seconds = timeout_seconds
        self.fallback_client = fallback_client or RuleBasedLLMClient()

    def analyze(
        self,
        function: FunctionIntent,
        alert: DriftAlert,
        prompt: str,
        session: TraceSessionSummary | None = None,
    ) -> RemediationReport:
        system = (
            "You are a production incident remediation assistant. Return strict JSON "
            "with keys: summary, risk, immediate_action, long_term_fix, supporting_facts."
        )
        try:
            payload, active_provider = call_ai_json_with_failsafe(
                system=system,
                user_prompt=prompt,
                preferred_provider=self.preferred_provider,
                timeout_seconds=self.timeout_seconds,
            )
            return _build_report_common(
                provider=active_provider,
                model_name=None,
                function=function,
                alert=alert,
                session=session,
                prompt=prompt,
                payload=payload,
            )
        except Exception as exc:
            report = self.fallback_client.analyze(function, alert, prompt, session=session)
            report.supporting_facts.append(f"Failsafe cascade resolved to rule-based fallback: {exc}")
            return report


def inspect_remediation_runtime(settings: object) -> RemediationRuntimeStatus:
    provider = str(getattr(settings, "remediation_provider", "auto") or "auto").strip().lower()
    model = getattr(settings, "remediation_model", None)
    base_url = getattr(settings, "remediation_base_url", None)
    enable = bool(getattr(settings, "enable_remediation_model", True))
    fallback_enabled = bool(getattr(settings, "remediation_fallback_enabled", True))
    blockers: list[str] = []

    available_map = get_available_ai_providers()

    if provider in ("rule-based", "deterministic") or not enable:
        return RemediationRuntimeStatus(
            provider="rule-based",
            model=None,
            base_url=None,
            enabled=enable,
            available=True,
            fallback_active=False,
            configured=True,
            blockers=blockers,
        )

    if provider in ("auto", "failsafe"):
        has_any = any(available_map.values())
        return RemediationRuntimeStatus(
            provider="failsafe",
            model=model,
            base_url=base_url,
            enabled=enable,
            available=has_any,
            fallback_active=fallback_enabled,
            configured=True,
            blockers=[],
        )

    if provider not in ("openai-compatible", "anthropic", "gemini", "antigravity"):
        blockers.append("Unsupported remediation provider configured.")

    configured = not blockers
    available = configured and available_map.get(provider, False)
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
    if status.provider in ("failsafe", "auto"):
        return FailsafeRemediationClient(
            preferred_provider=getattr(settings, "preferred_provider", None),
            timeout_seconds=float(getattr(settings, "remediation_timeout_seconds", 20.0)),
            fallback_client=fallback_client,
        )
    if status.provider == "openai-compatible":
        return OpenAICompatibleRemediationClient(
            base_url=str(status.base_url or "https://api.openai.com/v1"),
            model=str(status.model or "gpt-4o-mini"),
            api_key=getattr(settings, "remediation_api_key", None),
            timeout_seconds=float(getattr(settings, "remediation_timeout_seconds", 30.0)),
            fallback_client=fallback_client,
        )
    if status.provider == "anthropic":
        return AnthropicRemediationClient(
            model=str(status.model or "claude-3-5-sonnet-latest"),
            api_key=getattr(settings, "remediation_api_key", None),
            base_url=str(status.base_url or "https://api.anthropic.com"),
            timeout_seconds=float(getattr(settings, "remediation_timeout_seconds", 30.0)),
            fallback_client=fallback_client,
        )
    return FailsafeRemediationClient(fallback_client=fallback_client)
