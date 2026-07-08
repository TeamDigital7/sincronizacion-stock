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
        erp = BigQuerySource(
            self.config.bigquery, self.config.service_account
        ).fetch_erp_stock(names)
        detail = reconcile(erp, ecommerce)
        summary = summarize(detail)
        return ReconciliationResult(
            summary=summary,
            detail=detail,
            warnings=warnings,
            excel_bytes=build_excel(summary, detail),
        )

