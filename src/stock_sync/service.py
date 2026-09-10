from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

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


class StockReconciliationService:
    def __init__(self, config: AppConfig):
        self.config = config

    def run(self, selected_sites: list[str] | None = None) -> ReconciliationResult:
        names = selected_sites or list(self.config.shopify_sites)
        ecommerce_frames = []
        warnings = []
        for name in names:
            frame, site_warnings = ShopifySource(
                self.config.shopify_sites[name]
            ).fetch_inventory()
            ecommerce_frames.append(frame)
            warnings.extend(f"{name}: {warning}" for warning in site_warnings)
        ecommerce = pd.concat(ecommerce_frames, ignore_index=True)
        site_mapping = dict(self.config.erp_site_to_shopify_site)
        bigquery = BigQuerySource(self.config.bigquery, self.config.service_account)
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
        if not erp_sites:
            erp_sites = names
            site_mapping.update({name: name for name in names})
        erp = bigquery.fetch_erp_stock(erp_sites)
        selected_shopify_sites = set(names)
        if not erp.empty:
            erp["sitio_erp"] = erp["sitio"]
            erp["sitio"] = erp["sitio_erp"].map(site_mapping).fillna(erp["sitio_erp"])
            erp = erp[erp["sitio"].isin(selected_shopify_sites)]
        unmapped_erp_sites = sorted(
            set(erp.get("sitio_erp", pd.Series(dtype=str)).dropna().astype(str))
            - set(site_mapping)
        )
        warnings.extend(
            f"Sitio ERP sin homologación hacia Shopify: {site}"
            for site in unmapped_erp_sites
        )
        detail, reconcile_warnings = reconcile(erp, ecommerce)
        warnings.extend(reconcile_warnings)
        summary = summarize(detail)
        return ReconciliationResult(
            summary=summary,
            detail=detail,
            warnings=warnings,
            excel_bytes=build_excel(summary, detail),
        )
