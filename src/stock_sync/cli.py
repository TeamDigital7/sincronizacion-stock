from __future__ import annotations

import argparse
import os
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from .audit import audit_json_bytes, build_audit_record
from .config import AppConfig
from .service import StockReconciliationService


def main() -> None:
    parser = argparse.ArgumentParser(description="Conciliación ERP-Shopify")
    parser.add_argument(
        "--config",
        default=os.environ.get("STOCK_SYNC_CONFIG", ".streamlit/secrets.toml"),
        help="Ruta al archivo TOML de configuración",
    )
    parser.add_argument("--site", action="append", dest="sites")
    parser.add_argument("--output", help="Ruta opcional para guardar el Excel")
    parser.add_argument("--audit-output", help="Ruta para guardar el registro JSON")
    parser.add_argument(
        "--actor", default=os.environ.get("GITHUB_ACTOR", os.environ.get("USER", "cli"))
    )
    parser.add_argument(
        "--trigger", default="github-actions" if os.environ.get("GITHUB_ACTIONS") else "cli"
    )
    args = parser.parse_args()

    run_id = str(uuid4())
    started_at = datetime.now(UTC)
    config = None
    try:
        with Path(args.config).open("rb") as config_file:
            config = AppConfig.from_mapping(tomllib.load(config_file))
        result = StockReconciliationService(config).run(
            args.sites,
            trigger=args.trigger,
            actor=args.actor,
            run_id=run_id,
            started_at=started_at,
        )
    except Exception as exc:
        if args.audit_output:
            expected_date = None
            if config:
                expected_date = (
                    datetime.now(ZoneInfo(config.timezone)).date()
                    - timedelta(days=1)
                ).isoformat()
            record = build_audit_record(
                run_id=run_id,
                status="FAILED",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                trigger=args.trigger,
                actor=args.actor,
                selected_sites=args.sites or [],
                expected_stock_date=expected_date,
                error_message=f"{type(exc).__name__}: {exc}",
            )
            _write_bytes(args.audit_output, audit_json_bytes(record))
        raise
    if args.output:
        _write_bytes(args.output, result.excel_bytes)
    if args.audit_output:
        _write_bytes(args.audit_output, result.audit_json)
    global_summary = result.summary[result.summary["sitio"] == "GLOBAL"].iloc[0]
    print(
        f"run_id={result.run_id} "
        f"comparadas={int(global_summary['combinaciones_comparadas'])} "
        f"desincronizadas={int(global_summary['combinaciones_desincronizadas'])} "
        f"advertencias={len(result.warnings)}"
    )


def _write_bytes(path: str, content: bytes) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)


if __name__ == "__main__":
    main()
