import pandas as pd

from stock_sync.reconciliation import reconcile, summarize


def test_reconcile_full_outer_and_zero_tolerance():
    erp = pd.DataFrame(
        [
            {
                "sitio": "columbia",
                "id_producto": "SKU1",
                "codigo_tienda": "001",
                "stock_erp_sitio": 3,
            },
            {
                "sitio": "columbia",
                "id_producto": "SKU2",
                "codigo_tienda": "001",
                "stock_erp_sitio": 1,
            },
        ]
    )
    ecommerce = pd.DataFrame(
        [
            {
                "sitio": "columbia",
                "variant_sku": "SKU1",
                "id_tienda_forus": "001",
                "stock_disponible": 2,
            },
            {
                "sitio": "columbia",
                "variant_sku": "SKU3",
                "id_tienda_forus": "001",
                "stock_disponible": 4,
            },
            {
                "sitio": "columbia",
                "variant_sku": "SKU4",
                "id_tienda_forus": "001",
                "stock_disponible": 0,
            },
        ]
    )
    detail, warnings = reconcile(erp, ecommerce)
    assert warnings == []
    statuses = dict(
        zip(detail["id_producto"].fillna(detail["variant_sku"]), detail["estado_sincronizacion"])
    )
    assert statuses == {
        "SKU1": "DESINCRONIZADO",
        "SKU2": "NO_CREADO",
        "SKU3": "DESINCRONIZADO",
        "SKU4": "SINCRONIZADO",
    }
    summary = summarize(detail)
    assert summary.iloc[-1]["porcentaje_desincronizacion"] == 75.0


def test_reconcile_sums_duplicate_ecommerce_sku_instead_of_failing():
    erp = pd.DataFrame(
        [
            {
                "sitio": "columbia",
                "id_producto": "SKU1",
                "codigo_tienda": "001",
                "stock_erp_sitio": 5,
            },
        ]
    )
    ecommerce = pd.DataFrame(
        [
            {
                "sitio": "columbia",
                "variant_sku": "SKU1",
                "id_tienda_forus": "001",
                "stock_disponible": 2,
                "shopify_variant_id": "111",
            },
            {
                "sitio": "columbia",
                "variant_sku": "SKU1",
                "id_tienda_forus": "001",
                "stock_disponible": 3,
                "shopify_variant_id": "222",
            },
        ]
    )
    detail, warnings = reconcile(erp, ecommerce)
    assert len(warnings) == 1
    assert "SKU1" in warnings[0]
    assert "111" in warnings[0] and "222" in warnings[0]
    row = detail.iloc[0]
    assert row["shopify_variant_id"] == "111, 222"
    assert row["stock_disponible_ecommerce"] == 5
    assert row["estado_sincronizacion"] == "SINCRONIZADO"


def test_catalog_sku_without_location_inventory_is_desynchronized_not_missing():
    erp = pd.DataFrame(
        [
            {
                "sitio": "vans",
                "id_producto": "5418567",
                "codigo_tienda": "159",
                "stock_erp_sitio": 5,
            }
        ]
    )
    ecommerce = pd.DataFrame(
        columns=["sitio", "variant_sku", "id_tienda_forus", "stock_disponible"]
    )

    detail, _ = reconcile(
        erp,
        ecommerce,
        catalog_skus_by_site={"vans": {"5418567"}},
    )

    row = detail.iloc[0]
    assert row["presente_catalogo_shopify"]
    assert not row["presente_ecommerce"]
    assert row["estado_sincronizacion"] == "DESINCRONIZADO"


def test_sku_absent_from_shopify_catalog_is_not_created():
    erp = pd.DataFrame(
        [
            {
                "sitio": "vans",
                "id_producto": "NO-EXISTE",
                "codigo_tienda": "159",
                "stock_erp_sitio": 5,
            }
        ]
    )
    ecommerce = pd.DataFrame(
        columns=["sitio", "variant_sku", "id_tienda_forus", "stock_disponible"]
    )

    detail, _ = reconcile(erp, ecommerce, catalog_skus_by_site={"vans": {"5418567"}})

    assert detail.iloc[0]["estado_sincronizacion"] == "NO_CREADO"

