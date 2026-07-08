from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

from .config import ShopifySiteConfig, normalize_location_id

INVENTORY_QUERY = """
query InventoryItems($cursor: String) {
  inventoryItems(first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      sku
      tracked
      inventoryLevels(first: 250) {
        pageInfo { hasNextPage }
        nodes {
          location { id name }
          quantities(names: ["available"]) { name quantity updatedAt }
        }
      }
    }
  }
}
"""


class ShopifyError(RuntimeError):
    pass


class ShopifySource:
    def __init__(self, config: ShopifySiteConfig, timeout: int = 60):
        self.config = config
        self.timeout = timeout
        self.url = (
            f"https://{config.shop_domain}/admin/api/{config.api_version}/graphql.json"
        )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-Shopify-Access-Token": config.admin_access_token,
                "Content-Type": "application/json",
            }
        )

    def _query(self, cursor: str | None) -> dict[str, Any]:
        for attempt in range(5):
            response = self.session.post(
                self.url,
                json={"query": INVENTORY_QUERY, "variables": {"cursor": cursor}},
                timeout=self.timeout,
            )
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(min(2**attempt, 16))
                continue
            if not response.ok:
                raise ShopifyError(
                    f"{self.config.name}: Shopify respondió HTTP {response.status_code}"
                )
            payload = response.json()
            if payload.get("errors"):
                raise ShopifyError(f"{self.config.name}: {payload['errors']}")
            return payload["data"]["inventoryItems"]
        raise ShopifyError(f"{self.config.name}: reintentos agotados")

    def fetch_inventory(self) -> tuple[pd.DataFrame, list[str]]:
        rows: list[dict[str, Any]] = []
        warnings: list[str] = []
        cursor = None
        fetched_at = datetime.now(timezone.utc)
        while True:
            connection = self._query(cursor)
            for item in connection["nodes"]:
                sku = (item.get("sku") or "").strip()
                if not sku:
                    continue
                levels = item["inventoryLevels"]
                if levels["pageInfo"]["hasNextPage"]:
                    warnings.append(f"{sku}: más de 250 ubicaciones; resultado incompleto")
                for level in levels["nodes"]:
                    location = level["location"]
                    location_id = normalize_location_id(location["id"])
                    store_code = self.config.location_store_map.get(location_id)
                    if store_code is None:
                        warnings.append(
                            f"Ubicación sin mapeo: {location['name']} ({location_id})"
                        )
                        continue
                    quantities = {q["name"]: q for q in level["quantities"]}
                    available = quantities.get("available", {})
                    rows.append(
                        {
                            "sitio": self.config.name,
                            "variant_sku": sku,
                            "id_tienda_forus": store_code,
                            "stock_disponible": int(available.get("quantity", 0)),
                            "fecha_corte_ecommerce": available.get("updatedAt") or fetched_at,
                            "shopify_location_id": location_id,
                            "shopify_location_name": location["name"],
                            "tracked": bool(item.get("tracked")),
                        }
                    )
            page = connection["pageInfo"]
            if not page["hasNextPage"]:
                break
            cursor = page["endCursor"]
        frame = pd.DataFrame(
            rows,
            columns=[
                "sitio",
                "variant_sku",
                "id_tienda_forus",
                "stock_disponible",
                "fecha_corte_ecommerce",
                "shopify_location_id",
                "shopify_location_name",
                "tracked",
            ],
        )
        return frame, sorted(set(warnings))
