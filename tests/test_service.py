from types import SimpleNamespace

import pandas as pd
import pytest

from stock_sync.service import StockReconciliationService


def test_missing_yesterday_stock_stops_before_shopify(monkeypatch):
    calls = {"shopify": 0, "expected_date": None}

    class FakeBigQuery:
        def __init__(self, *args):
            pass

        def fetch_site_mapping(self):
            return pd.DataFrame()

        def fetch_erp_stock(self, sites, allowed_brands_by_site, expected_date):
            calls["expected_date"] = expected_date
            raise ValueError("No existe stock ERP para la fecha esperada")

    class FakeShopify:
        def __init__(self, *args):
            calls["shopify"] += 1

    monkeypatch.setattr("stock_sync.service.BigQuerySource", FakeBigQuery)
    monkeypatch.setattr("stock_sync.service.ShopifySource", FakeShopify)
    config = SimpleNamespace(
        shopify_sites={"rockford": object()},
        erp_site_to_shopify_site={"4": "rockford"},
        brand_by_shopify_site={"rockford": ("ROCKFORD", "COLUMBIA", "SOREL")},
        bigquery=SimpleNamespace(mode="query"),
        service_account={},
        timezone="America/Lima",
    )

    with pytest.raises(ValueError, match="fecha esperada"):
        StockReconciliationService(config).run(["rockford"])

    assert calls["expected_date"] is not None
    assert calls["shopify"] == 0
