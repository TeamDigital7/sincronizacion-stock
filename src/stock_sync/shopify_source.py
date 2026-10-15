from __future__ import annotations

import random
import time
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import requests

from .config import ShopifySiteConfig, normalize_location_id

INVENTORY_QUERY = """
query InventoryItems($cursor: String) {
  inventoryItems(first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      sku
      tracked
      variant { id }
      inventoryLevels(first: 250) {
        pageInfo { hasNextPage endCursor }
        nodes {
          location { id name }
          quantities(names: ["available"]) { name quantity updatedAt }
        }
      }
    }
  }
}
"""

INVENTORY_LEVELS_QUERY = """
query InventoryLevels($id: ID!, $cursor: String) {
  node(id: $id) {
    ... on InventoryItem {
      inventoryLevels(first: 250, after: $cursor) {
        pageInfo { hasNextPage endCursor }
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
        self.catalog_skus: set[str] = set()

    def _request(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(5):
            try:
                response = self.session.post(
                    self.url,
                    json={"query": query, "variables": variables},
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                if attempt == 4:
                    raise ShopifyError(
                        f"{self.config.name}: error de red después de 5 intentos"
                    ) from exc
                time.sleep(min(2**attempt, 16) + random.random())
                continue
            if response.status_code == 429 or response.status_code >= 500:
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else min(2**attempt, 16)
                except ValueError:
                    delay = min(2**attempt, 16)
                time.sleep(delay + random.random())
                continue
            if not response.ok:
                raise ShopifyError(
                    f"{self.config.name}: Shopify respondió HTTP {response.status_code}"
                )
            try:
                payload = response.json()
            except requests.exceptions.JSONDecodeError as exc:
                raise ShopifyError(
                    f"{self.config.name}: Shopify devolvió una respuesta no JSON"
                ) from exc
            if payload.get("errors"):
                throttled = any(
                    error.get("extensions", {}).get("code") == "THROTTLED"
                    for error in payload["errors"]
                )
                if throttled and attempt < 4:
                    time.sleep(min(2**attempt, 16) + random.random())
                    continue
                raise ShopifyError(f"{self.config.name}: {payload['errors']}")
            throttle = (
                payload.get("extensions", {})
                .get("cost", {})
                .get("throttleStatus", {})
            )
            available = float(throttle.get("currentlyAvailable", 0))
            restore_rate = float(throttle.get("restoreRate", 0))
            if restore_rate > 0 and available < 50:
                time.sleep((50 - available) / restore_rate)
            return payload
        raise ShopifyError(f"{self.config.name}: reintentos agotados")

    def _query(self, cursor: str | None) -> dict[str, Any]:
        payload = self._request(INVENTORY_QUERY, {"cursor": cursor})
        return payload["data"]["inventoryItems"]

    def _remaining_levels(self, item_id: str, cursor: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        while cursor:
            payload = self._request(
                INVENTORY_LEVELS_QUERY, {"id": item_id, "cursor": cursor}
            )
            node = payload.get("data", {}).get("node")
            if not node:
                raise ShopifyError(
                    f"{self.config.name}: no se pudo paginar el inventory item {item_id}"
                )
            connection = node["inventoryLevels"]
            rows.extend(connection["nodes"])
            page = connection["pageInfo"]
            cursor = page.get("endCursor") if page["hasNextPage"] else ""
        return rows

    def fetch_inventory(self) -> tuple[pd.DataFrame, list[str]]:
        rows: list[dict[str, Any]] = []
        warnings: list[str] = []
        cursor = None
        fetched_at = datetime.now(UTC)
        while True:
            connection = self._query(cursor)
            for item in connection["nodes"]:
                sku = (item.get("sku") or "").strip()
                if not sku:
                    continue
                self.catalog_skus.add(sku)
                variant = item.get("variant") or {}
                variant_id = (
                    normalize_location_id(variant["id"]) if variant.get("id") else None
                )
                levels = item["inventoryLevels"]
                level_nodes = list(levels["nodes"])
                if levels["pageInfo"]["hasNextPage"]:
                    level_nodes.extend(
                        self._remaining_levels(
                            item["id"], levels["pageInfo"]["endCursor"]
                        )
                    )
                for level in level_nodes:
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
                            "shopify_variant_id": variant_id,
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
                "shopify_variant_id",
                "tracked",
            ],
        )
        return frame, sorted(set(warnings))
