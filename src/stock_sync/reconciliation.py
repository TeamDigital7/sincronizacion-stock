from __future__ import annotations

import pandas as pd

DETAIL_COLUMNS = [
    "sitio", "sitio_erp", "nombre_sitio_erp", "id_producto", "variant_sku",
    "conca", "talla", "codigo_tienda", "id_tienda_forus", "stock_erp_sitio",
    "stock_disponible_ecommerce", "diferencia_stock", "diferencia_absoluta",
    "estado_sincronizacion", "presente_erp", "presente_ecommerce",
    "fecha_corte_erp", "fecha_corte_ecommerce", "nombrebodega",
    "shopify_location_name", "stock_seguridad_aplicado",
    "relacion_bodega_sitio_duplicada",
]


def _normalize_key(series: pd.Series) -> pd.Series:
    """Normaliza claves de cruce: castea a texto, recorta espacios y
    quita el sufijo ".0" que deja BigQuery al convertir columnas
    numéricas (FLOAT/NUMERIC) a STRING (ej. "5312506.0" -> "5312506")."""
    normalized = series.astype("string").str.strip()
    return normalized.str.replace(r"^(\d+)\.0$", r"\1", regex=True)


def reconcile(erp: pd.DataFrame, ecommerce: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    erp = erp.copy()
    ecommerce = ecommerce.copy()
    for frame, columns in (
        (erp, ["sitio", "id_producto", "codigo_tienda"]),
        (ecommerce, ["sitio", "variant_sku", "id_tienda_forus"]),
    ):
        for column in columns:
            frame[column] = _normalize_key(frame[column])

    ecommerce = ecommerce.rename(columns={"stock_disponible": "stock_disponible_ecommerce"})

    warnings: list[str] = []
    key = ["sitio", "variant_sku", "id_tienda_forus"]
    duplicated = ecommerce.duplicated(subset=key, keep=False)
    if duplicated.any():
        for (sitio, sku, tienda), _ in ecommerce[duplicated].groupby(key):
            warnings.append(
                f"{sitio}: SKU {sku} repetido en tienda {tienda} en Shopify; "
                "stock sumado entre los duplicados"
            )
        agg = {
            column: func
            for column, func in {
                "stock_disponible_ecommerce": "sum",
                "fecha_corte_ecommerce": "max",
                "shopify_location_id": "first",
                "shopify_location_name": "first",
                "tracked": "any",
            }.items()
            if column in ecommerce.columns
        }
        ecommerce = ecommerce.groupby(key, as_index=False).agg(agg)

    erp["_presente_erp"] = True
    ecommerce["_presente_ecommerce"] = True
    joined = erp.merge(
        ecommerce,
        how="outer",
        left_on=["sitio", "id_producto", "codigo_tienda"],
        right_on=["sitio", "variant_sku", "id_tienda_forus"],
        validate="one_to_one",
    )
    joined["presente_erp"] = joined["_presente_erp"].fillna(False).astype(bool)
    joined["presente_ecommerce"] = (
        joined["_presente_ecommerce"].fillna(False).astype(bool)
    )
    joined["stock_erp_sitio"] = joined["stock_erp_sitio"].fillna(0).astype(float)
    joined["stock_disponible_ecommerce"] = (
        joined["stock_disponible_ecommerce"].fillna(0).astype(float)
    )
    joined["diferencia_stock"] = (
        joined["stock_erp_sitio"] - joined["stock_disponible_ecommerce"]
    )
    joined["diferencia_absoluta"] = joined["diferencia_stock"].abs()

    def status(row: pd.Series) -> str:
        if not row["presente_erp"]:
            return "SOLO_ECOMMERCE"
        if not row["presente_ecommerce"]:
            return "SOLO_ERP"
        if row["diferencia_stock"] != 0:
            return "DIFERENCIA_STOCK"
        return "SINCRONIZADO"

    joined["estado_sincronizacion"] = joined.apply(status, axis=1)
    for column in DETAIL_COLUMNS:
        if column not in joined:
            joined[column] = pd.NA
    detail = joined[DETAIL_COLUMNS].sort_values(
        ["sitio", "diferencia_absoluta", "id_producto"],
        ascending=[True, False, True],
        na_position="last",
    )
    return detail, warnings


def summarize(detail: pd.DataFrame) -> pd.DataFrame:
    def aggregate(group: pd.DataFrame, site: str) -> dict:
        mismatch = group["estado_sincronizacion"] != "SINCRONIZADO"
        skus = group["id_producto"].fillna(group["variant_sku"])
        mismatch_skus = skus[mismatch]
        return {
            "sitio": site,
            "combinaciones_comparadas": len(group),
            "combinaciones_desincronizadas": int(mismatch.sum()),
            "porcentaje_desincronizacion": round(100 * mismatch.mean(), 2) if len(group) else 0,
            "skus_unicos": int(skus.nunique()),
            "skus_unicos_desincronizados": int(mismatch_skus.nunique()),
            "solo_erp": int((group["estado_sincronizacion"] == "SOLO_ERP").sum()),
            "solo_ecommerce": int(
                (group["estado_sincronizacion"] == "SOLO_ECOMMERCE").sum()
            ),
            "diferencia_absoluta_unidades": float(group["diferencia_absoluta"].sum()),
        }

    rows = [aggregate(group, str(site)) for site, group in detail.groupby("sitio")]
    rows.append(aggregate(detail, "GLOBAL"))
    return pd.DataFrame(rows)
