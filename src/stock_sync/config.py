from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

TABLE_ID = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_$-]+$")


def _plain(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return {k: _plain(v) for k, v in value.to_dict().items()}
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    return value


def _table(value: str, key: str) -> str:
    value = str(value).strip()
    if not TABLE_ID.fullmatch(value):
        raise ValueError(f"{key} debe tener formato proyecto.dataset.tabla")
    return value


@dataclass(frozen=True)
class BigQueryConfig:
    project_id: str
    job_project_id: str
    location: str
    stock_table: str
    warehouses_table: str
    warehouse_sites_table: str


@dataclass(frozen=True)
class ShopifySiteConfig:
    name: str
    shop_domain: str
    admin_access_token: str
    api_version: str
    location_store_map: dict[str, str]


@dataclass(frozen=True)
class AppConfig:
    bigquery: BigQueryConfig
    service_account: dict[str, Any]
    shopify_sites: dict[str, ShopifySiteConfig]
    timezone: str = "America/Lima"
    daily_refresh_time: str = "08:00"

    @classmethod
    def from_mapping(cls, source: Mapping[str, Any]) -> "AppConfig":
        data = _plain(source)
        bq = data["bigquery"]
        bigquery = BigQueryConfig(
            project_id=str(bq["project_id"]),
            job_project_id=str(bq.get("job_project_id", bq["project_id"])),
            location=str(bq.get("location", "US")),
            stock_table=_table(bq["stock_table"], "stock_table"),
            warehouses_table=_table(bq["warehouses_table"], "warehouses_table"),
            warehouse_sites_table=_table(
                bq["warehouse_sites_table"], "warehouse_sites_table"
            ),
        )
        sites = {}
        for name, raw in data.get("shopify_sites", {}).items():
            mapping = {
                normalize_location_id(k): str(v).strip()
                for k, v in raw.get("location_store_map", {}).items()
            }
            sites[name] = ShopifySiteConfig(
                name=name,
                shop_domain=str(raw["shop_domain"]).strip().removeprefix("https://").rstrip("/"),
                admin_access_token=str(raw["admin_access_token"]),
                api_version=str(raw.get("api_version", "2026-04")),
                location_store_map=mapping,
            )
        if not sites:
            raise ValueError("Debe configurarse al menos un sitio Shopify")
        return cls(
            bigquery=bigquery,
            service_account=dict(data["gcp_service_account"]),
            shopify_sites=sites,
            timezone=str(data.get("app", {}).get("timezone", "America/Lima")),
            daily_refresh_time=str(
                data.get("app", {}).get("daily_refresh_time", "08:00")
            ),
        )


def normalize_location_id(value: object) -> str:
    return str(value).strip().rsplit("/", 1)[-1]
