from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from lsa.drift.models import RemediationReport


@dataclass(slots=True)
class RemediationIndexRecord:
    recorded_at: str
    environment_name: str
    audit_id: str
    snapshot_id: str | None
    snapshot_path: str
    function: str
    risk: str
    title: str
    summary: str
    report_path: str
    remediation_provider: str
    remediation_model: str | None
    supporting_facts: list[str]

    def to_dict(self) -> dict:
        return {
            "recorded_at": self.recorded_at,
            "environment_name": self.environment_name,
            "audit_id": self.audit_id,
            "snapshot_id": self.snapshot_id,
            "snapshot_path": self.snapshot_path,
            "function": self.function,
            "risk": self.risk,
            "title": self.title,
            "summary": self.summary,
            "report_path": self.report_path,
            "remediation_provider": self.remediation_provider,
            "remediation_model": self.remediation_model,
            "supporting_facts": list(self.supporting_facts),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "RemediationIndexRecord":
        return cls(
            recorded_at=str(payload["recorded_at"]),
            environment_name=str(payload["environment_name"]),
            audit_id=str(payload["audit_id"]),
            snapshot_id=payload.get("snapshot_id"),
            snapshot_path=str(payload["snapshot_path"]),
            function=str(payload["function"]),
            risk=str(payload["risk"]),
            title=str(payload["title"]),
            summary=str(payload["summary"]),
            report_path=str(payload["report_path"]),
            remediation_provider=str(payload["remediation_provider"]),
            remediation_model=payload.get("remediation_model"),
            supporting_facts=[str(item) for item in payload.get("supporting_facts", [])],
        )


class RemediationIndexService:
    def __init__(self, index_path: str | Path, *, environment_name: str) -> None:
        self.index_path = Path(index_path)
        self.environment_name = environment_name

    def record_report(
        self,
        *,
        audit_id: str,
        snapshot_id: str | None,
        snapshot_path: str,
        report_path: str,
        report: RemediationReport,
        remediation_provider: str,
        remediation_model: str | None,
    ) -> RemediationIndexRecord:
        record = RemediationIndexRecord(
            recorded_at=datetime.now(UTC).isoformat(),
            environment_name=self.environment_name,
            audit_id=audit_id,
            snapshot_id=snapshot_id,
            snapshot_path=snapshot_path,
            function=report.function,
            risk=report.risk,
            title=report.title,
            summary=report.summary,
            report_path=report_path,
            remediation_provider=remediation_provider,
            remediation_model=remediation_model,
            supporting_facts=list(report.supporting_facts),
        )
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), sort_keys=True))
            handle.write("\n")
        return record

    def list_reports(
        self,
        *,
        limit: int = 100,
        function: str | None = None,
        risk: str | None = None,
        environment_name: str | None = None,
    ) -> list[RemediationIndexRecord]:
        if not self.index_path.exists():
            return []
        function_filter = function.strip() if function else None
        risk_filter = risk.strip().upper() if risk else None
        environment_filter = environment_name.strip().lower() if environment_name else None
        records: list[RemediationIndexRecord] = []
        with self.index_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    record = RemediationIndexRecord.from_dict(json.loads(raw))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    continue
                if function_filter and record.function != function_filter:
                    continue
                if risk_filter and record.risk.upper() != risk_filter:
                    continue
                if environment_filter and record.environment_name.lower() != environment_filter:
                    continue
                records.append(record)
        records.sort(key=lambda item: item.recorded_at, reverse=True)
        return records[: max(limit, 0)]
