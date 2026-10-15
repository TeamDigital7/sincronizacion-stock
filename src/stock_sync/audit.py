from __future__ import annotations

import json
from datetime import datetime
from typing import Any


def build_audit_record(
    *,
    run_id: str,
    status: str,
    started_at: datetime,
    trigger: str,
    actor: str,
    selected_sites: list[str],
    completed_at: datetime,
    metrics: dict[str, Any] | None = None,
    warning_count: int = 0,
    warnings: list[str] | None = None,
    expected_stock_date: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "status": status,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": (completed_at - started_at).total_seconds(),
        "trigger": trigger,
        "actor": actor,
        "selected_sites": selected_sites,
        "expected_stock_date": expected_stock_date,
        "warning_count": warning_count,
        "warnings": warnings or [],
        "metrics": metrics or {},
        "error_message": error_message[:4000] if error_message else None,
    }


def audit_json_bytes(record: dict[str, Any]) -> bytes:
    return json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
