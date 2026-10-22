from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd

from .audit import audit_json_bytes, build_audit_record
from .bigquery_source import BigQuerySource
from .config import AppConfig
from .reconciliation import reconcile, summarize
from .report import build_excel
from .shopify_source import ShopifySource


@dataclass
class ReconciliationResult:
    summary: pd.DataFrame
    detail: pd.DataFrame
    warnings: list[str]
    excel_bytes: bytes
    run_id: str
    started_at: datetime
    completed_at: datetime
    expected_stock_date: str
    audit_json: bytes


class StockReconciliationService:
    def __init__(self, config: AppConfig):
        self.config = config

    def run(
        self,
        selected_sites: list[str] | None = None,
        *,
        trigger: str = "manual",
        actor: str = "unknown",
        run_id: str | None = None,
        started_at: datetime | None = None,
    ) -> ReconciliationResult:
        names = (
            list(self.config.shopify_sites)
            if selected_sites is None
            else list(selected_sites)
        )
        if not names:
            raise ValueError("Debe seleccionarse al menos un sitio")
        unknown_sites = sorted(set(names) - set(self.config.shopify_sites))
        if unknown_sites:
            raise ValueError(f"Sitios Shopify desconocidos: {', '.join(unknown_sites)}")
        run_id = run_id or str(uuid4())
        started_at = started_at or datetime.now(UTC)
        bigquery = BigQuerySource(self.config.bigquery, self.config.service_account)
        return self._run(
            names,
            run_id=run_id,
            started_at=started_at,
            trigger=trigger,
            actor=actor,
            bigquery=bigquery,
        )

    def _run(
        self,
        names: list[str],
        *,
        run_id: str,
        started_at: datetime,
        trigger: str,
        actor: str,
        bigquery: BigQuerySource,
    ) -> ReconciliationResult:
        expected_date = (
            datetime.now(ZoneInfo(self.config.timezone)).date() - timedelta(days=1)
        )
        site_mapping = dict(self.config.erp_site_to_shopify_site)
        mapping_from_bigquery = pd.DataFrame()
        if self.config.bigquery.mode != "snapshot":
            mapping_from_bigquery = bigquery.fetch_site_mapping()
        if not mapping_from_bigquery.empty:
            site_mapping.update(
                dict(
                    zip(
                        mapping_from_bigquery["sitio_erp"].astype(str).str.strip(),
                        mapping_from_bigquery["sitio_shopify"].astype(str).str.strip(),
                    )
                )
            )
        erp_sites = [
            erp_site
            for erp_site, shopify_site in site_mapping.items()
            if shopify_site in set(names)
        ]
        unmapped_shopify_sites = sorted(set(names) - set(site_mapping.values()))
        if not erp_sites:
            raise ValueError(
                "Sitios Shopify sin homologación ERP en "
                "[site_mapping.erp_to_shopify]: " + ", ".join(unmapped_shopify_sites)
            )
        warnings = [
            f"Sitio Shopify sin homologación ERP: {site}; solo se compara contra Shopify"
            for site in unmapped_shopify_sites
        ]
        allowed_brands_by_erp_site = {
            erp_site: self.config.brand_by_shopify_site.get(shopify_site, ())
            for erp_site, shopify_site in site_mapping.items()
            if shopify_site in set(names)
        }
        erp = bigquery.fetch_erp_stock(
            erp_sites,
            allowed_brands_by_site=allowed_brands_by_erp_site,
            expected_date=expected_date,
        )
        ecommerce_frames = []
        catalog_skus_by_site: dict[str, set[str]] = {}
        for name in names:
            source = ShopifySource(self.config.shopify_sites[name])
            frame, site_warnings = source.fetch_inventory()
            ecommerce_frames.append(frame)
            catalog_skus_by_site[name] = source.catalog_skus
            warnings.extend(f"{name}: {warning}" for warning in site_warnings)
        ecommerce = pd.concat(ecommerce_frames, ignore_index=True)
        selected_shopify_sites = set(names)
        if not erp.empty:
            erp["sitio_erp"] = erp["sitio"]
            erp["sitio"] = erp["sitio_erp"].map(site_mapping).fillna(erp["sitio_erp"])
            erp = erp[erp["sitio"].isin(selected_shopify_sites)]
        detail, reconcile_warnings = reconcile(
            erp, ecommerce, catalog_skus_by_site=catalog_skus_by_site
        )
        warnings.extend(reconcile_warnings)
        summary = summarize(detail)
        completed_at = datetime.now(UTC)
        global_summary = summary[summary["sitio"] == "GLOBAL"].iloc[0]
        metrics = {
            "combinations_compared": int(global_summary["combinaciones_comparadas"]),
            "combinations_mismatched": int(
                global_summary["combinaciones_desincronizadas"]
            ),
            "unique_skus": int(global_summary["skus_unicos"]),
            "absolute_difference_units": float(
                global_summary["diferencia_absoluta_unidades"]
            ),
        }
        audit_json = audit_json_bytes(
            build_audit_record(
                run_id=run_id,
                status="COMPLETED",
                started_at=started_at,
                completed_at=completed_at,
                trigger=trigger,
                actor=actor,
                selected_sites=names,
                expected_stock_date=expected_date.isoformat(),
                warning_count=len(warnings),
                warnings=warnings,
                metrics=metrics,
            )
        )
        return ReconciliationResult(
            summary=summary,
            detail=detail,
            warnings=warnings,
            excel_bytes=build_excel(summary, detail),
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            expected_stock_date=expected_date.isoformat(),
            audit_json=audit_json,
        )
