import json
from datetime import UTC, datetime

from stock_sync.audit import audit_json_bytes, build_audit_record


def test_audit_json_records_run_metadata_and_metrics():
    started = datetime(2026, 10, 14, 13, 0, tzinfo=UTC)
    completed = datetime(2026, 10, 14, 13, 0, 12, tzinfo=UTC)
    record = build_audit_record(
        run_id="run-1",
        status="COMPLETED",
        started_at=started,
        completed_at=completed,
        trigger="test",
        actor="tester",
        selected_sites=["rockford"],
        expected_stock_date="2026-10-13",
        warning_count=2,
        metrics={"combinations_mismatched": 3},
    )

    decoded = json.loads(audit_json_bytes(record))
    assert decoded["duration_seconds"] == 12
    assert decoded["selected_sites"] == ["rockford"]
    assert decoded["expected_stock_date"] == "2026-10-13"
    assert decoded["metrics"]["combinations_mismatched"] == 3
