from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

TABLE_ID = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_$-]+$")
COLUMN_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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


def _required(mapping: Mapping[str, Any], key: str, section: str) -> Any:
    if key not in mapping or mapping[key] in (None, ""):
        raise ValueError(f"Falta [{section}].{key} en secrets.toml")
    return mapping[key]


def _column(value: str | None, key: str) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    value = str(value).strip()
    if not COLUMN_NAME.fullmatch(value):
        raise ValueError(f"{key} debe ser un nombre simple de columna BigQuery")
    return value


@dataclass(frozen=True)
class BigQueryConfig:
    project_id: str
    job_project_id: str
    location: str
    mode: str = "query"
    erp_snapshot_table: str | None = None
    stock_table: str | None = None
    warehouses_table: str | None = None
    warehouse_sites_table: str | None = None
    warehouse_sites_site_column: str = "idsitio"
    warehouse_sites_name_column: str | None = None
    warehouse_sites_warehouse_column: str | None = None
    warehouse_sites_warehouses_column: str | None = "bodegas"
    enabled_erp_site_ids: tuple[str, ...] = ("2", "4", "6", "24", "102", "103")
    site_mapping_table: str | None = None
    site_mapping_erp_column: str | None = None
    site_mapping_shopify_column: str | None = None


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
    erp_site_to_shopify_site: dict[str, str]
    timezone: str = "America/Lima"
    daily_refresh_time: str = "08:00"

    @classmethod
    def from_mapping(cls, source: Mapping[str, Any]) -> "AppConfig":
        data = _plain(source)
        bq = data["bigquery"]
        stock_table = bq.get("stock_table", bq.get("table"))
        erp_snapshot_table = bq.get("erp_snapshot_table", bq.get("snapshot_table"))
        mode = str(bq.get("mode", "query")).strip().lower()
        if mode not in {"query", "snapshot"}:
            raise ValueError("[bigquery].mode debe ser 'query' o 'snapshot'")
        bigquery = BigQueryConfig(
            project_id=str(bq["project_id"]),
            job_project_id=str(bq.get("job_project_id", bq["project_id"])),
            location=str(bq.get("location", "US")),
            mode=mode,
            erp_snapshot_table=(
                _table(
                    _required(
                        {"erp_snapshot_table": erp_snapshot_table},
                        "erp_snapshot_table",
                        "bigquery",
                    ),
                    "erp_snapshot_table",
                )
                if mode == "snapshot"
                else (_table(erp_snapshot_table, "erp_snapshot_table") if erp_snapshot_table else None)
            ),
            stock_table=(
                _table(_required({"stock_table": stock_table}, "stock_table", "bigquery"), "stock_table")
                if mode == "query"
                else (_table(stock_table, "stock_table") if stock_table else None)
            ),
            warehouses_table=(
                _table(_required(bq, "warehouses_table", "bigquery"), "warehouses_table")
                if mode == "query"
                else (_table(bq["warehouses_table"], "warehouses_table") if bq.get("warehouses_table") else None)
            ),
            warehouse_sites_table=(
                _table(
                    _required(
                        {
                            "warehouse_sites_table": bq.get(
                                "warehouse_sites_table", bq.get("sites_table")
                            )
                        },
                        "warehouse_sites_table",
                        "bigquery",
                    ),
                    "warehouse_sites_table",
                )
                if mode == "query"
                else (
                    _table(
                        bq.get("warehouse_sites_table", bq.get("sites_table")),
                        "warehouse_sites_table",
                    )
                    if bq.get("warehouse_sites_table", bq.get("sites_table"))
                    else None
                )
            ),
            warehouse_sites_site_column=_column(
                bq.get("warehouse_sites_site_column", "idsitio"),
                "warehouse_sites_site_column",
            )
            or "idsitio",
            warehouse_sites_name_column=_column(
                bq.get("warehouse_sites_name_column"),
                "warehouse_sites_name_column",
            ),
            warehouse_sites_warehouse_column=_column(
                bq.get("warehouse_sites_warehouse_column"),
                "warehouse_sites_warehouse_column",
            ),
            warehouse_sites_warehouses_column=_column(
                bq.get("warehouse_sites_warehouses_column", "bodegas"),
                "warehouse_sites_warehouses_column",
            ),
            enabled_erp_site_ids=tuple(
                str(value).strip()
                for value in bq.get(
                    "enabled_erp_site_ids", ["2", "4", "6", "24", "102", "103"]
                )
                if str(value).strip()
            ),
            site_mapping_table=(
                _table(bq["site_mapping_table"], "site_mapping_table")
                if bq.get("site_mapping_table")
                else None
            ),
            site_mapping_erp_column=_column(
                bq.get("site_mapping_erp_column"), "site_mapping_erp_column"
            ),
            site_mapping_shopify_column=_column(
                bq.get("site_mapping_shopify_column"), "site_mapping_shopify_column"
            ),
        )
        configured_site_mapping = data.get("site_mapping", {}).get("erp_to_shopify", {})
        erp_site_to_shopify_site = {
            str(erp).strip(): str(shopify).strip()
            for erp, shopify in configured_site_mapping.items()
            if str(erp).strip() and str(shopify).strip()
        }
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
            erp_site_to_shopify_site=erp_site_to_shopify_site,
            timezone=str(data.get("app", {}).get("timezone", "America/Lima")),
            daily_refresh_time=str(
                data.get("app", {}).get("daily_refresh_time", "08:00")
            ),
        )


def normalize_location_id(value: object) -> str:
    return str(value).strip().rsplit("/", 1)[-1]
