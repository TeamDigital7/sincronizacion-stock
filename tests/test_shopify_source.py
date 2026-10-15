from unittest.mock import patch

import requests

from stock_sync.config import ShopifySiteConfig
from stock_sync.shopify_source import ShopifySource


def _config():
    return ShopifySiteConfig(
        name="rockford",
        shop_domain="rockford.myshopify.com",
        admin_access_token="token",
        api_version="2026-04",
        location_store_map={"10": "001", "20": "002"},
    )


class FakeResponse:
    status_code = 200
    ok = True

    def __init__(self):
        self.headers = {}

    def json(self):
        return {"data": {"ok": True}}


def test_request_retries_a_network_error():
    source = ShopifySource(_config())
    calls = 0

    def post(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise requests.Timeout("timeout")
        return FakeResponse()

    source.session.post = post
    with patch("stock_sync.shopify_source.time.sleep"):
        assert source._request("query { ok }", {})["data"]["ok"] is True
    assert calls == 2


def test_fetch_inventory_includes_paginated_locations():
    source = ShopifySource(_config())
    source._query = lambda cursor: {
        "nodes": [
            {
                "id": "gid://shopify/InventoryItem/1",
                "sku": "SKU1",
                "tracked": True,
                "variant": {"id": "gid://shopify/ProductVariant/2"},
                "inventoryLevels": {
                    "pageInfo": {"hasNextPage": True, "endCursor": "next"},
                    "nodes": [
                        {
                            "location": {
                                "id": "gid://shopify/Location/10",
                                "name": "Tienda 1",
                            },
                            "quantities": [{"name": "available", "quantity": 3}],
                        }
                    ],
                },
            }
        ],
        "pageInfo": {"hasNextPage": False, "endCursor": None},
    }
    source._remaining_levels = lambda item_id, cursor: [
        {
            "location": {
                "id": "gid://shopify/Location/20",
                "name": "Tienda 2",
            },
            "quantities": [{"name": "available", "quantity": 4}],
        }
    ]

    frame, warnings = source.fetch_inventory()

    assert warnings == []
    assert frame["stock_disponible"].tolist() == [3, 4]
    assert frame["id_tienda_forus"].tolist() == ["001", "002"]
    assert source.catalog_skus == {"SKU1"}
