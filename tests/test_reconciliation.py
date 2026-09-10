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
        ]
    )
    detail, warnings = reconcile(erp, ecommerce)
    assert warnings == []
    statuses = dict(
        zip(detail["id_producto"].fillna(detail["variant_sku"]), detail["estado_sincronizacion"])
    )
    assert statuses == {
        "SKU1": "DIFERENCIA_STOCK",
        "SKU2": "SOLO_ERP",
        "SKU3": "SOLO_ECOMMERCE",
    }
    summary = summarize(detail)
    assert summary.iloc[-1]["porcentaje_desincronizacion"] == 100


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
            },
            {
                "sitio": "columbia",
                "variant_sku": "SKU1",
                "id_tienda_forus": "001",
                "stock_disponible": 3,
            },
        ]
    )
    detail, warnings = reconcile(erp, ecommerce)
    assert len(warnings) == 1
    assert "SKU1" in warnings[0]
    row = detail.iloc[0]
    assert row["stock_disponible_ecommerce"] == 5
    assert row["estado_sincronizacion"] == "SINCRONIZADO"

