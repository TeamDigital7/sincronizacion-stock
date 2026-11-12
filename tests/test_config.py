import pytest

from stock_sync.config import AppConfig


def base_config(site: dict) -> dict:
    return {
        "bigquery": {
            "mode": "snapshot",
            "project_id": "project",
            "erp_snapshot_table": "project.dataset.snapshot",
        },
        "gcp_service_account": {},
        "shopify_sites": {"sitio_incompleto": site},
    }


def test_missing_shop_domain_identifies_site() -> None:
    with pytest.raises(
        ValueError,
        match=r"Falta \[shopify_sites\.sitio_incompleto\]\.shop_domain",
    ):
        AppConfig.from_mapping(base_config({"admin_access_token": "token"}))


def test_missing_admin_token_identifies_site() -> None:
    with pytest.raises(
        ValueError,
        match=r"Falta \[shopify_sites\.sitio_incompleto\]\.admin_access_token",
    ):
        AppConfig.from_mapping(base_config({"shop_domain": "shop.myshopify.com"}))
